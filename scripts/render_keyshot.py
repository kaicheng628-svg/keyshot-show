"""Load with runpy inside KeyShot, injecting lux; call run(job_json, mode)."""
from pathlib import Path
import math
import runpy
import time
import traceback

helpers = runpy.run_path(str(Path(__file__).with_name('keyshot_job.py')))
load_job = helpers['load_job']
write_json = helpers['write_json']
frame_path = helpers['frame_path']
valid_png = helpers['valid_png']
rotate = helpers['rotate']


def run(config_path, mode='render'):
    if 'lux' not in globals():
        raise RuntimeError('Run this script inside KeyShot with lux injected')
    cfg = load_job(config_path, mode)
    stage = helpers['prepare_stage'](cfg)
    progress_path = Path(cfg['work_dir']) / 'progress.json'
    width, height = cfg['render_width'], cfg['render_height']
    ready = {(m['id'], i) for m in cfg['models'] for i in range(cfg['count'])
             if valid_png(frame_path(cfg, m, i), width, height)}
    total = len(cfg['models']) * cfg['count']
    rendered = 0
    start = time.time()
    camera = None

    def status(value, **extra):
        data = dict(status=value, mode=mode, completed=len(ready), total=total,
                    rendered_this_run=rendered, elapsed_seconds=round(time.time()-start, 2),
                    fingerprint=cfg['fingerprint'], stage=str(stage), **extra)
        write_json(progress_path, data)
        return data

    try:
        for model in cfg['models']:
            if all((model['id'], i) in ready for i in range(cfg['count'])):
                continue
            if (Path(cfg['work_dir']) / 'STOP').exists():
                return status('stopped')
            source = Path(model['source'])
            resources = stage / model['id'] / 'resources'
            resources.mkdir(parents=True, exist_ok=True)
            if source.suffix.lower() == '.ksp':
                lux.openPackage(path=str(source), resources=str(resources))
            else:
                lux.openFile(path=str(source))
            lux.setRenderEngine(lux.RENDER_ENGINE_PRODUCT_GPU if cfg['engine'] == 'gpu' else lux.RENDER_ENGINE_PRODUCT)
            lux.pause()
            # Preserve the source camera in memory; never save over the user's scene.
            camera = (lux.getCameraPosition(), lux.getCameraDirection(), lux.getCameraUp())
            lux.setCameraDistance(lux.getCameraDistance() * model['distance_scale'])
            pivot = model.get('pivot', lux.getCameraLookAt())
            if 'pivot' in model:
                lux.setCameraLookAt(pt=tuple(pivot))
            position, direction, up = lux.getCameraPosition(), lux.getCameraDirection(), lux.getCameraUp()
            offset = tuple(position[j]-pivot[j] for j in range(3))
            rd = lux.getRenderOptions().getDict()
            rd['render_mode'] = lux.RENDER_MODE_SAMPLES
            rd['progressive_max_samples'] = cfg['render_samples']
            opts = lux.RenderOptions(dict=rd)
            opts.setAddToQueue(False)
            opts.setBackgroundRendering(False)
            opts.setMaxSamplesRendering(cfg['render_samples'])
            opts.setOutputAlphaChannel(False)
            for i in range(cfg['count']):
                if (model['id'], i) in ready:
                    continue  # Skip before any camera update or render.
                if (Path(cfg['work_dir']) / 'STOP').exists():
                    return status('stopped')
                if rendered >= cfg['max_frames_per_run']:
                    return status('batch_complete')
                angle = cfg['direction'] * 2 * math.pi * i / cfg['count']
                delta = rotate(offset, angle, cfg['axis'])
                lux.setCameraPosition(tuple(pivot[j]+delta[j] for j in range(3)))
                lux.setCameraDirection(rotate(direction, angle, cfg['axis']))
                lux.setCameraUp(rotate(up, angle, cfg['axis']))
                final = frame_path(cfg, model, i)
                temp = final.with_name(final.stem + '.partial.png')
                final.parent.mkdir(parents=True, exist_ok=True)
                if temp.exists():
                    temp.unlink()  # Only this task's unfinished frame.
                began = time.time()
                result = lux.renderImage(path=str(temp), width=width, height=height, opts=opts)
                lux.pause()
                if not result or not valid_png(temp, width, height):
                    raise RuntimeError('Render failed or invalid PNG: ' + str(temp))
                temp.replace(final)
                ready.add((model['id'], i))
                rendered += 1
                status('rendering', model=model['id'], frame=i+1,
                       frame_seconds=round(time.time()-began, 2))
            lux.setCameraPosition(camera[0])
            lux.setCameraDirection(camera[1])
            lux.setCameraUp(camera[2])
            camera = None
        return status('complete')
    except Exception:
        status('error', error=traceback.format_exc())
        raise
    finally:
        if camera is not None:
            lux.setCameraPosition(camera[0])
            lux.setCameraDirection(camera[1])
            lux.setCameraUp(camera[2])
            lux.pause()
