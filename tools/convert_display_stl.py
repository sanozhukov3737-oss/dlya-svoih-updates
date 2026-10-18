"""Convert a licensed, already reviewed binary STL exterior to a self-contained GLB.

No mesh simplification or added mechanical detail. STL millimetres/Z-up become
glTF metres/Y-up; exact duplicate position/normal pairs share an index.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import struct


def convert(source, target):
    raw = source.read_bytes()
    if len(raw) < 84:
        raise ValueError('Not a binary STL')
    count = struct.unpack_from('<I', raw, 80)[0]
    if not count or len(raw) != 84 + count * 50:
        raise ValueError('Invalid binary STL size')
    vertices, normals, indices, unique = [], [], [], {}
    for face in struct.iter_unpack('<12fH', raw[84:]):
        if not all(math.isfinite(v) for v in face[:12]):
            raise ValueError('Non-finite STL coordinates')
        nx, ny, nz = face[:3]
        length = math.sqrt(nx * nx + ny * ny + nz * nz)
        if length < 0.99 or length > 1.01:
            raise ValueError('STL normal is not a unit vector')
        normal = (nx, nz, -ny)
        for offset in (3, 6, 9):
            x, y, z = face[offset:offset + 3]
            position = (x * 0.001, z * 0.001, -y * 0.001)
            key = struct.pack('<6f', *position, *normal)
            if key not in unique:
                unique[key] = len(vertices)
                vertices.append(position)
                normals.append(normal)
            indices.append(unique[key])
    position_bytes = b''.join(struct.pack('<3f', *v) for v in vertices)
    normal_bytes = b''.join(struct.pack('<3f', *v) for v in normals)
    index_bytes = struct.pack('<' + 'I' * len(indices), *indices)
    binary = position_bytes + normal_bytes + index_bytes
    model = {
        'asset': {'version': '2.0', 'generator': 'DLYA SVOIH binary STL display conversion'},
        'scene': 0, 'scenes': [{'nodes': [0]}], 'nodes': [{'mesh': 0}],
        'meshes': [{'primitives': [{'attributes': {'POSITION': 0, 'NORMAL': 1}, 'indices': 2, 'material': 0}]}],
        'materials': [{'name': 'Neutral display material (source STL has no colour)', 'pbrMetallicRoughness': {
            'baseColorFactor': [0.55, 0.55, 0.55, 1], 'metallicFactor': 0, 'roughnessFactor': 0.85}}],
        'buffers': [{'byteLength': len(binary)}],
        'bufferViews': [
            {'buffer': 0, 'byteOffset': 0, 'byteLength': len(position_bytes), 'target': 34962},
            {'buffer': 0, 'byteOffset': len(position_bytes), 'byteLength': len(normal_bytes), 'target': 34962},
            {'buffer': 0, 'byteOffset': len(position_bytes) + len(normal_bytes), 'byteLength': len(index_bytes), 'target': 34963},
        ],
        'accessors': [
            {'bufferView': 0, 'componentType': 5126, 'count': len(vertices), 'type': 'VEC3',
             'min': [min(v[i] for v in vertices) for i in range(3)], 'max': [max(v[i] for v in vertices) for i in range(3)]},
            {'bufferView': 1, 'componentType': 5126, 'count': len(normals), 'type': 'VEC3'},
            {'bufferView': 2, 'componentType': 5125, 'count': len(indices), 'type': 'SCALAR'},
        ],
    }
    document = json.dumps(model, separators=(',', ':')).encode()
    document += b' ' * (-len(document) % 4)
    binary += b'\0' * (-len(binary) % 4)
    output = (struct.pack('<4sII', b'glTF', 2, 28 + len(document) + len(binary))
              + struct.pack('<I4s', len(document), b'JSON') + document
              + struct.pack('<I4s', len(binary), b'BIN\0') + binary)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(output)
    return {'triangles': count, 'vertices': len(vertices), 'bytes': len(output),
            'originalSha256': hashlib.sha256(raw).hexdigest(), 'packagedSha256': hashlib.sha256(output).hexdigest()}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('target', type=Path)
    args = parser.parse_args()
    print(json.dumps(convert(args.source, args.target), indent=2))
