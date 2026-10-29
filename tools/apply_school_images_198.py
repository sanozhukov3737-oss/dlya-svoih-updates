"""Apply exterior-image corrections to the exact, corrected first PDF batch."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OVERLAY=ROOT/'content/overlays/school-images-20261028.json'

def apply(source,output,overlay=None):
    raw=Path(source).read_bytes();data=json.loads(raw);o=json.loads((Path(overlay) if overlay else OVERLAY).read_text())
    if hashlib.sha256(raw).hexdigest()!=o['baseCatalogSha256'] or data['contentVersion']!=198:
        raise ValueError('Requires the exact corrected first batch, not an already-applied catalog')
    cards={c['id']:c for c in data['cards']};rowids={c['rowid'] for c in data['cards']}
    for change in o['changes']:
        c=cards[change['cardId']]
        for k,v in change['before'].items():
            if c.get(k)!=v:raise ValueError(f'Unexpected field: {c["id"]}/{k}')
        c.update(copy.deepcopy(change['after']))
    for c in o['cards']:
        if c['id'] in cards or c['rowid'] in rowids:raise ValueError('Duplicate new identity')
        if c['contentStatus']!='source_only' or c['verifiedAt'] is not None:raise ValueError('Source-only record required')
        data['cards'].append(c)
    Path(output).parent.mkdir(parents=True,exist_ok=True)
    Path(output).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    return o['summary']
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--output',required=True);p.add_argument('--overlay');a=p.parse_args();print(json.dumps(apply(a.source,a.output,a.overlay),ensure_ascii=False))
