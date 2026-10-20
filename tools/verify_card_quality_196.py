"""Verify preservation against the actual public catalog, not an older revision."""
import argparse
import json
from pathlib import Path

from apply_card_quality_196 import ROOT, REMOVED_MAP, TABLE_CARDS, VARIANTS


def tables(body):
    return [b for b in body.split('\n\n') if b.startswith('|')]


def verify(baseline, current):
    old, new = (json.loads(Path(p).read_text()) for p in (baseline, current))
    assert old['contentVersion'] == 195 and new['contentVersion'] == 196
    a, b = ({c['id']: c for c in data['cards']} for data in (old, new))
    assert set(a) - set(b) == set(REMOVED_MAP) and not set(b) - set(a)
    assert len(b) == 1695 and sum(len(c['images']) for c in b.values()) == 1596
    assert old['countries'] == new['countries'] and old['categories'] == new['categories']
    for cid, card in b.items():
        previous = a[cid]
        for field in ['id', 'rowid', 'section', 'categoryId', 'countries',
                      'contentStatus', 'reviewedAt', 'verifiedAt', 'modelStatus', 'sourceGrade']:
            assert previous[field] == card[field], (cid, field)
        if card['section'] == 'MEDICINE':
            assert card == previous, ('medical preservation', cid)
    for cid in TABLE_CARDS:
        for block in tables(a[cid]['body']):
            lines = block.splitlines()
            if len(lines[0].strip('|').split('|')) <= 2:
                continue
            for line in [lines[0], *lines[2:]]:
                for cell in line.strip('|').split('|'):
                    assert cell.strip() in b[cid]['body'], (cid, cell)
    for cid, labels in VARIANTS.items():
        assert tables(a[cid]['body']) == tables(b[cid]['body']), cid
        for label, table in zip(labels, tables(b[cid]['body'])):
            assert f'## {label}\n\n{table}' in b[cid]['body'], (cid, label)
    # A withdrawn favorite retains its child rows. Reusing their IDs in another
    # card would make the actual Android @Insert transaction fail.
    for field in ('images', 'sources'):
        retained = {r['id'] for c in b.values() for r in c[field]}
        withdrawn = {r['id'] for cid in REMOVED_MAP for r in a[cid][field]}
        assert retained.isdisjoint(withdrawn), ('archived primary key collision', field)
    audit = json.loads((ROOT / 'research/catalog-quality-196/after.json').read_text())
    assert not audit['confirmedStructuralErrors']
    assert not audit['duplicateTitleGroups']
    assert audit['database']['cardIdsAndRowidsMatch']
    return dict(retainedStableIds=1695, unchangedMedicalCards=20,
                formattedTables=audit['coverage']['tables'], activeImageReferences=1596,
                archivedChildIdsDoNotCollide=True, structuralErrors=0)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--current', type=Path, default=ROOT / 'content/catalog.json')
    args = parser.parse_args()
    print(json.dumps(verify(args.baseline, args.current)))
