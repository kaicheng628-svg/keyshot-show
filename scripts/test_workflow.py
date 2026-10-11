"""Offline behavioral tests with a fake lux API; no KeyShot UI or real scenes touched."""
import argparse
import json
import math
from pathlib import Path
import runpy
import tempfile
from PIL import Image
from keyshot_job import load_job, frame_path, valid_png
from encode_video import encode


class Options:
    def __init__(self, **kwargs):
        self.data = kwargs.get('dict', {})
    def getDict(self): return dict(self.data)
    def setAddToQueue(self, value): pass
    def setBackgroundRendering(self, value): pass
    def setMaxSamplesRendering(self, value): self.data['samples'] = value
    def setOutputAlphaChannel(self, value): pass


class FakeLux:
    RENDER_ENGINE_PRODUCT_GPU = 3
    RENDER_ENGINE_PRODUCT = 0
    RENDER_MODE_SAMPLES = 1
    RenderOptions = Options
    def __init__(self):
        self.calls = []
        self.fail = False
        self.openPackage()
    def openPackage(self, **kwargs):
        self.pivot = (2, 3, 4)
        self.pos, self.direction, self.up = (2, 3, 14), (0, 0, -1), (0, 1, 0)
    def openFile(self, **kwargs): self.openPackage()
    def setRenderEngine(self, value): pass
    def pause(self): pass
    def getCameraPosition(self): return self.pos
    def getCameraDirection(self): return self.direction
    def getCameraUp(self): return self.up
    def getCameraLookAt(self): return self.pivot
    def getCameraDistance(self): return math.dist(self.pos, self.pivot)
    def setCameraDistance(self, value):
        self.pos = tuple(self.pivot[i]-self.direction[i]*value for i in range(3))
    def setCameraPosition(self, value): self.pos = value
    def setCameraDirection(self, value): self.direction = value
    def setCameraUp(self, value): self.up = value
    def getRenderOptions(self): return Options()
    def renderImage(self, path, width, height, opts):
        if self.fail: return False
        radius = math.dist(self.pos, self.pivot)
        assert abs(radius-12.5) < 1e-7
        aim = tuple((self.pivot[j]-self.pos[j])/radius for j in range(3))
        assert math.dist(aim, self.direction) < 1e-7, 'Camera lost orbit center'
        self.calls.append((path, self.pos))
        color = tuple(int((v+1)*100) for v in self.direction)
        Image.new('RGB', (width, height), color).save(path)
        return True


def test(ffmpeg, ffprobe):
    with tempfile.TemporaryDirectory(prefix='keyshot-show-test-') as tmp:
        root = Path(tmp)
        source = root/'模型.ksp'
        source.write_bytes(b'offline test fixture, not a KeyShot scene')
        cfg = dict(work_dir=str(root/'work'), output_dir=str(root/'output'),
                   duration=4, fps=3, width=64, height=48, max_frames_per_run=5,
                   ffmpeg=ffmpeg, ffprobe=ffprobe,
                   models=[dict(id='测试模型', source=str(source))])
        config = root/'job.json'
        config.write_text(json.dumps(cfg, ensure_ascii=False), encoding='utf-8')
        fake = FakeLux()
        run = runpy.run_path(str(Path(__file__).with_name('render_keyshot.py')),
                            init_globals={'lux': fake})['run']
        assert run(config, 'preview')['status'] == 'batch_complete'
        assert run(config, 'preview')['status'] == 'complete'
        assert len(fake.calls) == 8
        assert Path(encode(config, preview=True)[0]['contact']).is_file()
        fake.calls.clear()
        assert run(config)['completed'] == 5
        assert run(config)['completed'] == 10
        assert run(config)['status'] == 'complete'
        assert len(fake.calls) == 12
        assert len({tuple(round(x, 6) for x in p) for _, p in fake.calls}) == 12
        assert run(config)['status'] == 'complete' and len(fake.calls) == 12
        normalized = load_job(config)
        frame = frame_path(normalized, normalized['models'][0], 4)
        frame.write_bytes(frame.read_bytes()[:-8])
        assert not valid_png(frame, 64, 48)
        assert run(config)['status'] == 'complete' and len(fake.calls) == 13
        report = encode(config)[0]
        assert report['decode_ok'] and report['video']['nb_frames'] == '12'
        try:
            encode(config)
        except FileExistsError:
            pass
        else:
            raise AssertionError('Existing output was overwritten')
        original_stage = normalized['stage']
        cfg['samples'] = 96
        config.write_text(json.dumps(cfg), encoding='utf-8')
        assert load_job(config)['stage'] != original_stage
        stop = root/'work'/'STOP'
        stop.touch()
        assert run(config)['status'] == 'stopped'
        stop.unlink()
        fake.fail = True
        try:
            run(config)
        except RuntimeError:
            pass
        else:
            raise AssertionError('False render return was accepted')
        status = json.loads((root/'work'/'progress.json').read_text(encoding='utf-8'))
        assert status['status'] == 'error' and status['completed'] == 0
        assert fake.pos == (2, 3, 14), 'Original camera not restored'
        print('PASS: orbit, preview, batching, resume, corrupt-frame repair, parameter isolation, STOP, failed-render rejection, camera restoration, real MP4 encode/probe/decode, overwrite protection')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ffmpeg', required=True)
    parser.add_argument('--ffprobe', required=True)
    args = parser.parse_args()
    test(args.ffmpeg, args.ffprobe)
