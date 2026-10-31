"""Restore the exact saved catalog 199 ZIP from checked public assets and delta bytes.

The recipe preserves original ZIP headers and deflate streams. The result must
match the previously reviewed package byte for byte before Android may test it.
"""
import argparse
import hashlib
import json
from pathlib import Path
import zlib

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_SHA256 = 'e4cd470d909f851a89a4eff90dffb7e7bbe24a7573ee575cb59d2b49c9c64a09'
EXPECTED_BYTES = 145570775

def sha(data):
    return hashlib.sha256(data).hexdigest()

def restore(output):
    folder = ROOT / 'content/releases/catalog199'
    recipe = json.loads((folder / 'recipe.json').read_text())
    assert recipe['formatVersion'] == 1
    assert (recipe['sha256'], recipe['bytes']) == (EXPECTED_SHA256, EXPECTED_BYTES)
    payload = bytearray()
    for part in recipe['parts']:
        assert Path(part['path']).name == part['path']
        data = (folder / part['path']).read_bytes()
        assert len(data) == part['bytes'] and sha(data) == part['sha256'], part['path']
        payload.extend(data)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix('.tmp')
    try:
        with temporary.open('wb') as destination:
            for segment in recipe['segments']:
                if segment[0] == 'literal':
                    _, offset, length = segment
                    assert 0 <= offset <= offset + length <= len(payload)
                    destination.write(payload[offset:offset+length])
                else:
                    kind, name, length, digest = segment
                    assert kind == 'asset' and name.startswith(('images/', 'thumbs/'))
                    assert len(Path(name).parts) == 2 and '..' not in Path(name).parts
                    data = (ROOT / 'app/src/main/assets' / name).read_bytes()
                    encoder = zlib.compressobj(9, zlib.DEFLATED, -15)
                    data = encoder.compress(data) + encoder.flush()
                    assert len(data) == length and sha(data) == digest, name
                    destination.write(data)
        assert temporary.stat().st_size == EXPECTED_BYTES
        with temporary.open('rb') as stream:
            assert hashlib.file_digest(stream, 'sha256').hexdigest() == EXPECTED_SHA256
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
    print(json.dumps(dict(bytes=EXPECTED_BYTES, sha256=EXPECTED_SHA256, exactSavedCandidate=True)))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    restore(parser.parse_args().output)
