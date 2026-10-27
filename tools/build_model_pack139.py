"""Package the unchanged reviewed models as an optional, independently removable ZIP."""
import gzip
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'app/src/main/assets/viewer3d'
OUT = ROOT / 'build/models139'

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    registry = gzip.decompress((ROOT/'content/models-0.3.138.json.gz').read_bytes())
    assert hashlib.sha256(registry).hexdigest() == 'e62321912e9c8b3da7f77d09eaeadf5383dc9a1f259d7f22d10642f48e41daab'
    models = json.loads(registry)['models']
    archive = OUT/'models-615-v1.zip'
    files = {}
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for m in models:
            raw = (ASSETS/m['file']).read_bytes()
            assert hashlib.sha256(raw).hexdigest() == m['packagedSha256'], m['id']
            info = zipfile.ZipInfo(m['file'], date_time=(2026,10,27,0,0,0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            z.writestr(info, raw, compresslevel=6)
            files[m['file']] = {'bytes':len(raw), 'sha256':m['packagedSha256']}
    with archive.open('rb') as stream: digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    descriptor = {'formatVersion':1, 'version':1, 'modelCount':len(models),
        'bytes':archive.stat().st_size, 'sha256':digest,
        'url':'https://github.com/sanozhukov3737-oss/dlya-svoih-updates/releases/download/models-pack-1/models-615-v1.zip',
        'expandedBytes':sum(f['bytes'] for f in files.values()), 'files':files}
    (OUT/'pack.json').write_text(json.dumps(descriptor, ensure_ascii=False, separators=(',',':'))+'\n')
    (ASSETS/'pack.json').write_bytes((OUT/'pack.json').read_bytes())
    (ASSETS/'models.json').write_bytes(registry)
    print(json.dumps({k:v for k,v in descriptor.items() if k!='files'}), flush=True)

if __name__ == '__main__': main()
