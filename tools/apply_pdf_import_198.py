"""Apply the reviewed, exterior-only PDF reference overlay to catalog 197.

The prepared batch is not a published update. Existing card IDs, rowids, text,
images and review grades are preserved. New entries retain source_only status.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OVERLAY = ROOT / 'content/overlays/pdf-import-20261028.json'


def apply(source, output):
    data = json.loads(Path(source).read_text(encoding='utf-8'))
    overlay = json.loads(OVERLAY.read_text(encoding='utf-8'))
    if hashlib.sha256(Path(source).read_bytes()).hexdigest() != overlay['baseCatalogSha256']:
        raise ValueError('The source differs from the reviewed catalog 197 baseline')
    if data['contentVersion'] != overlay['baseContentVersion']:
        raise ValueError('This overlay requires the exact catalog 197 baseline')
    original = copy.deepcopy(data['cards'])
    cards = {c['id']: c for c in data['cards']}
    rowids = {c['rowid'] for c in data['cards']}
    for table in ('countries', 'categories'):
        known = {r['id']: r for r in data[table]}
        for row in overlay[table]:
            if row['id'] in known:
                raise ValueError(f'Duplicate {table} entry: {row["id"]}')
            data[table].append(row)
    for row in overlay['cards']:
        if row['id'] in cards or row['rowid'] in rowids:
            raise ValueError('A new reference collides with a published card')
        if row['contentStatus'] != 'source_only' or row['verifiedAt'] is not None:
            raise ValueError('Unverified PDF references cannot acquire verified status')
        data['cards'].append(row)
        cards[row['id']] = row
        rowids.add(row['rowid'])
    for change in overlay['enrichments']:
        card = cards[change['cardId']]
        if change['images']:
            raise ValueError('This reviewed batch has no confirmed photo replacements')
        ids = {s['id'] for s in card['sources']}
        for row in change['sources']:
            if row['id'] not in ids:
                card['sources'].append(row)
                ids.add(row['id'])
    for old in original:
        after = cards[old['id']]
        for key in old:
            if key != 'sources' and after[key] != old[key]:
                raise ValueError(f'Published field changed: {old["id"]}/{key}')
    data['contentVersion'] = overlay['targetContentVersion']
    data['catalogVersion'] = overlay['targetContentVersion']
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(output).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return {'cards': len(data['cards']), 'newCards': len(overlay['cards']),
            'newImages': sum(len(c['images']) for c in overlay['cards']),
            'originalCardsPreserved': len(original)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, default=ROOT / 'content/catalog.json')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(apply(args.source, args.output), ensure_ascii=False))
