"""External Python CLI; requires Pillow and configured FFmpeg/FFprobe."""
import argparse
from fractions import Fraction
import json
from pathlib import Path
import subprocess
from PIL import Image
from keyshot_job import load_job, frame_path, valid_png, write_json, file_hash


def encode(config_path, preview=False, selected=None):
    cfg = load_job(config_path, 'preview' if preview else 'render')
    models = [m for m in cfg['models'] if not selected or m['id'] == selected]
    if not models:
        raise ValueError('Unknown model id: ' + str(selected))
    reports = []
    output_dir = Path(cfg['output_dir'])
    output_dir.mkdir(parents=True, exist_ok=True)
    # Validate every selected model before producing any video.
    for model in models:
        for i in range(cfg['count']):
            path = frame_path(cfg, model, i)
            if not valid_png(path, cfg['render_width'], cfg['render_height']):
                raise RuntimeError('Missing or invalid frame: ' + str(path))
            with Image.open(path) as im:
                im.load()
    for model in models:
        folder = frame_path(cfg, model, 0).parent
        count = min(12, cfg['count'])
        indices = [i*cfg['count']//count for i in range(count)]
        thumb_width = 320
        thumb_height = round(thumb_width * cfg['render_height'] / cfg['render_width'])
        contact = Image.new('RGB', (thumb_width*4, thumb_height*((count+3)//4)), 'white')
        for index, frame in enumerate(indices):
            with Image.open(frame_path(cfg, model, frame)) as im:
                contact.paste(im.convert('RGB').resize((thumb_width, thumb_height)),
                              ((index%4)*thumb_width, (index//4)*thumb_height))
        contact_path = folder / 'contact.jpg'
        contact.save(contact_path, quality=95)
        if preview:
            reports.append(dict(model=model['id'], contact=str(contact_path)))
            continue
        output = output_dir / (model['id'] + '_360_' + str(cfg['duration']) + 's.mp4')
        if output.exists():
            raise FileExistsError('Will not overwrite existing video: ' + str(output))
        temp = output.with_name(output.stem + '.partial.mp4')
        subprocess.run([cfg['ffmpeg'], '-hide_banner', '-loglevel', 'error', '-y',
                        '-framerate', str(cfg['fps']), '-start_number', '0', '-i',
                        str(folder/'frame_%04d.png'), '-frames:v', str(cfg['count']), '-an',
                        '-c:v', 'libx264', '-preset', 'slow', '-crf', '18', '-pix_fmt',
                        'yuv420p', '-movflags', '+faststart', str(temp)], check=True)
        probe = json.loads(subprocess.check_output([
            cfg['ffprobe'], '-v', 'error', '-select_streams', 'v:0', '-show_entries',
            'stream=codec_name,width,height,pix_fmt,r_frame_rate,nb_frames,duration',
            '-of', 'json', str(temp)]))
        stream = probe['streams'][0]
        if not (int(stream['nb_frames']) == cfg['count'] and
                abs(float(stream['duration'])-cfg['duration']) < 0.001 and
                stream['width'] == cfg['width'] and stream['height'] == cfg['height'] and
                Fraction(stream['r_frame_rate']) == cfg['fps'] and
                stream['codec_name'] == 'h264' and stream['pix_fmt'] == 'yuv420p'):
            raise RuntimeError('Video metadata mismatch: ' + str(stream))
        subprocess.run([cfg['ffmpeg'], '-hide_banner', '-loglevel', 'error', '-xerror',
                        '-i', str(temp), '-f', 'null', '-'], check=True)
        temp.rename(output)
        report = dict(model=model['id'], file=str(output), bytes=output.stat().st_size,
                      sha256=file_hash(output), fingerprint=cfg['fingerprint'],
                      video=stream, contact=str(contact_path), decode_ok=True)
        write_json(folder/'verification.json', report)
        reports.append(report)
    return reports


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('config')
    parser.add_argument('--preview', action='store_true')
    parser.add_argument('--model')
    args = parser.parse_args()
    print(json.dumps(encode(args.config, args.preview, args.model), ensure_ascii=False, indent=2))
