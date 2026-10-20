"""Apply reviewed physical measurements for five exact artillery models."""
import csv
import json
from fill_reference_specs_v146 import ROOT, apply, audit


def update(data, patches):
    result = apply(data, patches)
    captions_corrected = []
    for card in data['cards']:
        if card['id'] != 'ordnance-v29-ga-0049':
            continue
        for picture in card['images']:
            old = '155 мм M1064 illuminating'
            if old in picture.get('caption', ''):
                picture['caption'] = picture['caption'].replace(old, '105 мм M1064 illuminating')
                captions_corrected.append(picture['id'])
    result['captions_corrected'] = captions_corrected
    if result['added'] or result['existing_tables_exposed'] or captions_corrected:
        data['contentVersion'] = max(data['contentVersion'], 102)
    return result


if __name__ == '__main__':
    path = ROOT / 'content/catalog.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    patches = json.loads((ROOT / 'content/reference_specs_v154.json').read_text(encoding='utf-8'))
    result = update(data, patches)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    rows = list(audit(data))
    with (ROOT / 'docs/ALL_CARDS_TTX_AUDIT.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({'added': len(result['added']), 'captions_corrected': len(result['captions_corrected']), 'audited': len(rows), 'ammunition_without_specs_section': sum(row['section'] == 'AMMUNITION' and row['specs_section'] == 'no' for row in rows)}, ensure_ascii=False))
