"""Apply reviewed physical data from the next primary-source batch."""
import csv
import json
from fill_reference_specs_v146 import ROOT, apply, audit

CORRECTIONS = {
    'ordnance-v29-ga-0042': [('стр. 3-21—3-22', 'стр. 3-15—3-16 (таблица дымовых выстрелов M60 с белым фосфором)')],
    'ref-v8-pomz-2': [('Проверенная полная масса и размеры\n\n', '')],
    'ref-v8-pmd-6': [('Индивидуальные размеры и полная масса\n\n', '')],
    'ref-v9-su-tm41': [('Согласованные размеры и полная масса советской модели\n\n', '')],
    'ref-v9-mv5': [('Подтверждённые габариты и полная масса конкретного изделия.', 'Полная масса конкретного изделия не подтверждена выбранной таблицей; размеры приведены в разделе ТТХ.')],
    'ref-v9-vpf': [('Подтверждённые габариты и полная масса конкретного изделия.', 'Полная масса конкретного изделия не подтверждена выбранной таблицей; размеры приведены в разделе ТТХ.')],
    'ref-v9-muv': [('Независимая проверка габаритов и полной массы конкретного исполнения.', 'Размеры базового МУВ приведены в ТТХ. Полная масса и характеристики остальных исполнений требуют отдельного подтверждения.')],
}

def update(data, patches):
    result = apply(data, patches)
    for card in data['cards']:
        if card['id'] not in result['added']:
            continue
        for old, new in CORRECTIONS.get(card['id'], []):
            assert old in card['body'], (card['id'], old)
            card['body'] = card['body'].replace(old, new)
    if result['added'] or result['existing_tables_exposed']:
        data['contentVersion'] = max(data['contentVersion'], 96)
    return result

if __name__ == '__main__':
    path = ROOT / 'content/catalog.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    patches = json.loads((ROOT / 'content/reference_specs_v148.json').read_text(encoding='utf-8'))
    result = update(data, patches)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    rows = list(audit(data))
    with (ROOT / 'docs/ALL_CARDS_TTX_AUDIT.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({'added': len(result['added']), 'audited': len(rows), 'ammunition_without_specs_section': sum(r['section'] == 'AMMUNITION' and r['specs_section'] == 'no' for r in rows)}, ensure_ascii=False))
