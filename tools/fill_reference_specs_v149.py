"""Apply reviewed physical data from the next primary-source batch."""
import csv
import json
from fill_reference_specs_v146 import ROOT, apply, audit

CORRECTIONS = {}

def update(data, patches):
    result = apply(data, patches)
    for card in data['cards']:
        if card['id'] not in result['added']:
            continue
        for old, new in CORRECTIONS.get(card['id'], []):
            assert old in card['body'], (card['id'], old)
            card['body'] = card['body'].replace(old, new)
    if result['added'] or result['existing_tables_exposed']:
        data['contentVersion'] = max(data['contentVersion'], 97)
    return result

if __name__ == '__main__':
    path = ROOT / 'content/catalog.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    patches = json.loads((ROOT / 'content/reference_specs_v149.json').read_text(encoding='utf-8'))
    result = update(data, patches)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    rows = list(audit(data))
    with (ROOT / 'docs/ALL_CARDS_TTX_AUDIT.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({'added': len(result['added']), 'audited': len(rows), 'ammunition_without_specs_section': sum(r['section'] == 'AMMUNITION' and r['specs_section'] == 'no' for r in rows)}, ensure_ascii=False))
