"""Restore only SHA-pinned exterior assets from the one-time import transport."""
from pathlib import Path
import hashlib
import json
import re
import zipfile
import io
import sys

ROOT=Path(__file__).resolve().parents[1]
MANIFEST=ROOT/'content/inputs/pdf198-assets-manifest.json'

def materialize():
    m=json.loads(MANIFEST.read_text())
    parts=[]
    for part in m['parts']:
        p=ROOT/part['path'];data=p.read_bytes()
        assert len(data)==part['bytes'] and hashlib.sha256(data).hexdigest()==part['sha256']
        parts.append(data)
    raw=b''.join(parts)
    assert len(raw)==m['bytes'] and hashlib.sha256(raw).hexdigest()==m['sha256']
    known={r['path']:r for r in m['files']}
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        assert len(z.namelist())==len(known) and set(z.namelist())==set(known)
        for name in z.namelist():
            assert re.fullmatch(r'(?:images|thumbs)/pdf198-[a-f0-9]{12}\.(?:webp|jpg)',name)
            info=z.getinfo(name);expected=known[name]
            assert info.file_size==expected['bytes'] and info.file_size<=4*1024*1024
            data=z.read(name);assert hashlib.sha256(data).hexdigest()==expected['sha256']
            target=ROOT/'app/src/main/assets'/name;target.parent.mkdir(exist_ok=True,parents=True)
            target.write_bytes(data)
    return {'restoredFiles':len(known),'sha256':m['sha256']}

def prune():
    overlay=json.loads((ROOT/'content/overlays/pdf-import-20261028.json').read_text())
    wanted={im[k] for c in overlay['cards'] for im in c['images'] for k in ('localPath','thumbnailPath')}
    assets=ROOT/'app/src/main/assets';removed=[]
    for folder in ('images','thumbs'):
        for path in (assets/folder).glob('pdf198-*'):
            if str(path.relative_to(assets)) not in wanted:
                removed.append(str(path.relative_to(assets)));path.unlink()
    return {'removedUnusedBatchAssets':removed}

if __name__=='__main__':print(json.dumps(prune() if '--prune' in sys.argv else materialize()))
