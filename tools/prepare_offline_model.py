"""Package the user-supplied CC BY exterior display model; preserve mesh bytes."""
import hashlib
import io
import json
from pathlib import Path
import struct
import sys
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL_SHA256 = '5607f9b98bedcd178d6d5ec9da593d262de8d739b04bea26bc8cc638f667f107'

def prepare(source):
    original = Path(source).read_bytes()
    assert hashlib.sha256(original).hexdigest() == ORIGINAL_SHA256
    assert struct.unpack_from('<4sII', original) == (b'glTF', 2, len(original))
    size, kind = struct.unpack_from('<II', original, 12)
    assert kind == 0x4e4f534a
    data = json.loads(original[20:20 + size])
    bin_size, bin_kind = struct.unpack_from('<II', original, 20 + size)
    assert bin_kind == 0x004e4942
    binary = original[28 + size:28 + size + bin_size]
    assert len(data['buffers']) == 1 and 'uri' not in data['buffers'][0]
    assert not data.get('extensionsRequired')
    images = {image['bufferView']: (i, image) for i, image in enumerate(data['images'])}
    colors = {data['textures'][m['pbrMetallicRoughness']['baseColorTexture']['index']]['source'] for m in data['materials']}
    output = bytearray()
    for index, view in enumerate(data['bufferViews']):
        value = binary[view.get('byteOffset', 0):view.get('byteOffset', 0) + view['byteLength']]
        assert len(value) == view['byteLength']
        if index in images:
            number, image = images[index]
            with Image.open(io.BytesIO(value)) as loaded:
                texture = loaded.convert('RGB')
                texture.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
                encoded = io.BytesIO()
                if number in colors:
                    texture.save(encoded, format='JPEG', quality=88, subsampling=0, optimize=True)
                    image['mimeType'] = 'image/jpeg'
                else:
                    texture.save(encoded, format='PNG', optimize=True)
                    image['mimeType'] = 'image/png'
                value = encoded.getvalue()
        output.extend(b'\x00' * (-len(output) % 4))
        view['byteOffset'] = len(output)
        view['byteLength'] = len(value)
        output.extend(value)
    data['buffers'][0]['byteLength'] = len(output)
    data['asset']['generator'] += '; DLYA SVOIH display texture optimization'
    encoded_json = json.dumps(data, ensure_ascii=False, separators=(',', ':')).encode()
    encoded_json += b' ' * (-len(encoded_json) % 4)
    output.extend(b'\x00' * (-len(output) % 4))
    packed = struct.pack('<4sII', b'glTF', 2, 12 + 8 + len(encoded_json) + 8 + len(output))
    packed += struct.pack('<II', len(encoded_json), 0x4e4f534a) + encoded_json
    packed += struct.pack('<II', len(output), 0x004e4942) + output
    directory = ROOT / 'app/src/main/assets/viewer3d'
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'tm-46.glb').write_bytes(packed)
    credits = dict(cardId='ref-v8-tm-46', title='ТМ-46', author='Oscar Goldsworthy',
        source='https://sketchfab.com/3d-models/tm-46-anti-tank-landmine-3f3ef18d34764342934e96c508d488b0',
        license='CC BY 4.0', licenseUrl='https://creativecommons.org/licenses/by/4.0/',
        modifications='Textures reduced from 2048 to 1024 pixels; base color textures encoded as JPEG. Mesh buffers unchanged.',
        originalSha256=ORIGINAL_SHA256, packagedSha256=hashlib.sha256(packed).hexdigest(),
        bytes=len(packed), resources='All model buffers and textures are embedded; no remote resources.')
    (directory / 'model-credits.json').write_text(json.dumps(credits, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'originalBytes':len(original), 'packagedBytes':len(packed), 'sha256':credits['packagedSha256']}))

if __name__ == '__main__':
    prepare(sys.argv[1])
