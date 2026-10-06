"""Apply reviewed physical characteristics and audit every catalogue card.

The patch contains source-specific item mass and dimensions, not operational data.
Existing card ids, media, favourites and reading records remain stable.
"""
import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC_HEADING = re.compile(r'^## .*?(?:ТТХ|характеристик)', re.M | re.I)
PHYSICAL_ROW = re.compile(r'^\|[^|]*(?:масса|габарит|диаметр|длина|ширина|высота)[^|]*\|[^|]*\d', re.M | re.I)

def apply(data, patches):
    changed = []
    normalized = []
    for card in data['cards']:
        body = card['body']
        patch = patches.get(card['id'])
        if patch and not SPEC_HEADING.search(body):
            assert patch['rows'] and patch['source']['url']
            table = '\n'.join('| ' + name + ' | ' + value.replace('|', '/') + ' |' for name, value in patch['rows'])
            block = '## ТТХ\n\n| Параметр | Значение |\n| --- | --- |\n' + table
            if patch.get('note'):
                block += '\n\n' + patch['note']
            block += '\n\nИсточник: ' + patch['source']['title'] + '.\n\n'
            anchor = re.search(r'^## (?:Внешний вид|Ограничения сведений|При обнаружении)', body, re.M)
            if anchor:
                body = body[:anchor.start()].rstrip() + '\n\n' + block + body[anchor.start():]
            else:
                body = body.rstrip() + '\n\n' + block
            if not any(s['id'] == patch['source']['id'] for s in card['sources']):
                card['sources'].append(patch['source'])
            if card['id'] == 'ref-v8-ptm-4':
                body = body.replace('Подтверждённые габариты и полная масса самой мины\n\n', '')
            changed.append(card['id'])
        # Existing physical measurements must be visible under a TTX heading too.
        blocks = re.split(r'(?=^## )', body, flags=re.M)
        for i, block in enumerate(blocks):
            if block.startswith('## Справочные сведения\n') and PHYSICAL_ROW.search(block) and not SPEC_HEADING.search(body):
                blocks[i] = block.replace('## Справочные сведения', '## ТТХ', 1)
                normalized.append(card['id'])
        card['body'] = ''.join(blocks)
    if changed or normalized:
        data['contentVersion'] = max(data['contentVersion'], 94)
    return {'added': changed, 'existing_tables_exposed': normalized}

def audit(data):
    for card in data['cards']:
        body = card['body']
        yield {
            'id': card['id'], 'title': card['title'], 'section': card['section'],
            'category': card['categoryId'],
            'specs_section': 'yes' if SPEC_HEADING.search(body) else 'no',
            'physical_numeric_table': 'yes' if PHYSICAL_ROW.search(body) else 'no',
            'sources': '; '.join(s['title'] for s in card['sources']),
        }

if __name__ == '__main__':
    path = ROOT / 'content/catalog.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    patches = json.loads((ROOT / 'content/reference_specs_v146.json').read_text(encoding='utf-8'))
    result = apply(data, patches)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    rows = list(audit(data))
    (ROOT / 'docs').mkdir(exist_ok=True)
    with (ROOT / 'docs/ALL_CARDS_TTX_AUDIT.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    print(json.dumps({'added': len(result['added']), 'existing_tables_exposed': len(result['existing_tables_exposed']), 'audited': len(rows), 'missing_section': sum(row['specs_section'] == 'no' for row in rows)}, ensure_ascii=False))
