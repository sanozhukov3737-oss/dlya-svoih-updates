"""Create an offline update ZIP with a validated database and SHA-256 manifest.
Checksums detect corruption; packages are not signed or authenticated in v0.2.1.
"""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
import zipfile
from build_catalog import ROOT, ASSETS, build

def make_pack(source, output):
    source, output = Path(source), Path(output)
    data = json.loads(source.read_text(encoding='utf-8'))
    media = sorted({image[key] for card in data['cards'] for image in card['images'] for key in ['localPath','thumbnailPath']})
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as directory:
        db_path = Path(directory) / 'guide.db'
        build(source, db_path)
        files = [('guide.db', db_path)] + [(name, ASSETS / name) for name in media]
        manifest = {'formatVersion': 1, 'contentVersion': data['contentVersion'], 'files': [
            {'path': name, 'bytes': path.stat().st_size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()} for name, path in files]}
        temp = output.with_suffix('.tmp')
        try:
            with zipfile.ZipFile(temp, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
                archive.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False, separators=(',', ':')))
                for name, path in files:
                    archive.write(path, name)
            temp.replace(output)
        finally:
            temp.unlink(missing_ok=True)
    return {'contentVersion': data['contentVersion'], 'files': len(files) + 1, 'bytes': output.stat().st_size}

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, default=ROOT / 'content/catalog.json')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(make_pack(args.source, args.output)))
