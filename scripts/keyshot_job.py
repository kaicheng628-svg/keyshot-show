"""Standard-library helpers shared by KeyShot and external encoding."""
import hashlib
import json
import math
from pathlib import Path
import re
import struct
import zlib


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(path)


def file_hash(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def load_job(path, mode='render'):
    if mode not in ('render', 'preview'):
        raise ValueError('mode must be render or preview')
    cfg = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    defaults = dict(duration=4, fps=30, width=1920, height=1080, samples=64,
                    preview_samples=32, distance_scale=1.25, axis='y',
                    direction=-1, engine='gpu', max_frames_per_run=60)
    cfg = dict(defaults, **cfg)
    for key in ('width', 'height', 'fps', 'samples', 'preview_samples', 'max_frames_per_run'):
        if type(cfg[key]) is not int or cfg[key] <= 0:
            raise ValueError(key + ' must be a positive integer')
    if cfg['width'] % 2 or cfg['height'] % 2:
        raise ValueError('H.264 output width and height must be even')
    count = cfg['duration'] * cfg['fps']
    if not math.isfinite(count) or count < 2 or abs(count-round(count)) > 1e-8:
        raise ValueError('duration * fps must be an integer >= 2')
    if cfg['axis'] not in ('x', 'y', 'z') or cfg['direction'] not in (-1, 1):
        raise ValueError('invalid axis or direction')
    if cfg['engine'] not in ('cpu', 'gpu'):
        raise ValueError('engine must be cpu or gpu')
    for key in ('work_dir', 'output_dir'):
        if not Path(cfg[key]).is_absolute():
            raise ValueError(key + ' must be absolute')
    ids = set()
    models = []
    for item in cfg['models']:
        model = dict(item)
        name = model['id']
        reserved = re.fullmatch(r'(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])', name, re.I)
        if (not name or re.search(r'[<>:"/\\|?*\x00-\x1f]', name) or
                name.endswith(('.', ' ')) or name in ('.', '..') or reserved or
                name.casefold() in ids):
            raise ValueError('Model ids must be unique safe filenames: ' + name)
        ids.add(name.casefold())
        source = Path(model['source'])
        if not source.is_absolute() or not source.is_file() or source.suffix.lower() not in ('.ksp', '.bip'):
            raise ValueError('Missing absolute KSP/BIP source: ' + str(source))
        model['source'] = str(source.resolve())
        model['sha256'] = file_hash(source)
        model['distance_scale'] = model.get('distance_scale', cfg['distance_scale'])
        if not math.isfinite(model['distance_scale']) or model['distance_scale'] <= 0:
            raise ValueError('distance_scale must be positive')
        if 'pivot' in model and (len(model['pivot']) != 3 or not all(math.isfinite(v) for v in model['pivot'])):
            raise ValueError('pivot must have three finite numbers')
        models.append(model)
    if not models:
        raise ValueError('No models configured')
    cfg['models'] = models
    cfg['count'] = 8 if mode == 'preview' else round(count)
    cfg['render_width'] = min(960, cfg['width']) if mode == 'preview' else cfg['width']
    cfg['render_height'] = (max(2, round(cfg['height'] * cfg['render_width'] / cfg['width'] / 2) * 2)
                            if mode == 'preview' else cfg['height'])
    cfg['render_samples'] = cfg['preview_samples'] if mode == 'preview' else cfg['samples']
    spec = {k: cfg[k] for k in ('models', 'count', 'render_width', 'render_height',
                               'render_samples', 'axis', 'direction', 'engine', 'fps')}
    spec['workflow_version'] = 1
    fingerprint = hashlib.sha256(json.dumps(spec, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    cfg['fingerprint'] = fingerprint
    cfg['stage'] = str(Path(cfg['work_dir']) / mode / fingerprint[:16])
    cfg['mode'] = mode
    return cfg


def prepare_stage(cfg):
    stage = Path(cfg['stage'])
    stage.mkdir(parents=True, exist_ok=True)
    manifest = stage / 'manifest.json'
    if manifest.exists():
        if json.loads(manifest.read_text(encoding='utf-8'))['fingerprint'] != cfg['fingerprint']:
            raise RuntimeError('Stage fingerprint collision; use a new work directory')
    else:
        write_json(manifest, cfg)
    return stage


def frame_path(cfg, model, index):
    return Path(cfg['stage']) / model['id'] / ('frame_%04d.png' % index)


def valid_png(path, width, height):
    """Validate PNG framing, dimensions, every chunk CRC, IDAT and final IEND."""
    try:
        with open(path, 'rb') as f:
            if f.read(8) != b'\x89PNG\r\n\x1a\n':
                return False
            first, pixels = True, False
            while True:
                header = f.read(8)
                if len(header) != 8:
                    return False
                length, kind = struct.unpack('>I4s', header)
                if length > 256 * 1024 * 1024:
                    return False
                payload, crc = f.read(length), f.read(4)
                if len(payload) != length or len(crc) != 4:
                    return False
                if (zlib.crc32(payload, zlib.crc32(kind)) & 0xffffffff) != struct.unpack('>I', crc)[0]:
                    return False
                if first:
                    if kind != b'IHDR' or length != 13 or struct.unpack('>II', payload[:8]) != (width, height):
                        return False
                    first = False
                if kind == b'IDAT':
                    pixels = True
                if kind == b'IEND':
                    return pixels and length == 0 and f.read(1) == b''
    except (OSError, ValueError, struct.error):
        return False


def rotate(vector, angle, axis='y'):
    x, y, z = vector
    c, s = math.cos(angle), math.sin(angle)
    if axis == 'x':
        return (x, c*y-s*z, s*y+c*z)
    if axis == 'y':
        return (c*x+s*z, y, -s*x+c*z)
    return (c*x-s*y, s*x+c*y, z)
