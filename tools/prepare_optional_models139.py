"""Prepare only metadata for the small APK; no model geometry is bundled."""
import gzip
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def main():
    registry = gzip.decompress((ROOT/'content/models-0.3.138.json.gz').read_bytes())
    assert hashlib.sha256(registry).hexdigest() == 'e62321912e9c8b3da7f77d09eaeadf5383dc9a1f259d7f22d10642f48e41daab'
    models = json.loads(registry)['models']
    descriptor = (ROOT/'content/model-pack-1.json').read_bytes()
    pack = json.loads(descriptor)
    assert len(models) == len(pack['files']) == pack['modelCount'] == 615
    for model in models: assert model['packagedSha256'] == pack['files'][model['file']]['sha256']
    assets = ROOT/'app/src/main/assets/viewer3d'
    (assets/'models.json').write_bytes(registry)
    (assets/'pack.json').write_bytes(descriptor)
    (assets/'card-index.json').write_text(json.dumps(sorted({c for m in models for c in m['cardIds']}),
        ensure_ascii=False,separators=(',',':'))+'\n')
    print('Prepared metadata for 615 optional models; APK assets exclude all GLBs')

if __name__ == '__main__': main()
