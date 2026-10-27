"""Restore the exact approved GLB bytes from the versioned build input."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'app/src/main/assets/viewer3d'

def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path)
    args = parser.parse_args()
    request = json.loads((ROOT/'docs/releases/app-0.3.138-inputs.json').read_text())
    registry = gzip.decompress((ROOT/'content/models-0.3.138.json.gz').read_bytes())
    assert hashlib.sha256(registry).hexdigest() == request['modelsSha256']
    (ASSETS/'models.json').write_bytes(registry)
    models = json.loads(registry)['models']
    (ASSETS/'card-index.json').write_text(json.dumps(sorted({c for m in models for c in m['cardIds']}),
        ensure_ascii=False,separators=(',',':'))+'\n')
    archive = args.archive or ROOT/'build/model-inputs'/request['archiveName']
    if not archive.exists():
        archive.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(['gh','release','download','models-0.3.138-inputs',
            '--repo','sanozhukov3737-oss/dlya-svoih-updates','--pattern',request['archiveName'],
            '--dir',str(archive.parent)],check=True,timeout=900)
    assert archive.stat().st_size == request['archiveBytes']
    assert sha(archive) == request['archiveSha256'], 'Input archive changed'
    with zipfile.ZipFile(archive) as z:
        assert set(z.namelist()) == set(request['newFiles'])
        for name, digest in request['newFiles'].items():
            assert Path(name).name == name and name.endswith('.glb')
            raw = z.read(name)
            assert hashlib.sha256(raw).hexdigest() == digest, name
            (ASSETS/name).write_bytes(raw)
    assert sha(ASSETS/'models.json') == request['modelsSha256']
    assert sha(ROOT/'app/src/main/assets/database/guide-v29.db') == request['databaseSha256']
    print('Restored 596 exact GLB files; model registry and catalog hashes verified')

if __name__ == '__main__':
    main()
