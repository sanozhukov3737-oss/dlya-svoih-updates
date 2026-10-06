"""Apply reviewed physical data from the next primary-source batch."""
import csv
import json
from fill_reference_specs_v146 import ROOT, apply, audit

CORRECTIONS = {
    'ref-v9-vn-mn79': [('Размеры и полная масса', 'Отдельная спецификация MN79 и полная масса требуют дальнейшей проверки.')],
    'ref-v9-vn-mbv78a1-a2': [('Раздельные размеры и полная масса вариантов', 'Размеры MBV78A1 и полная масса обоих вариантов требуют дальнейшего подтверждения.')],
    'ref-v8-za-no8-at': [('Полная масса и внешние размеры', 'Полная масса изделия требует дальнейшего подтверждения.')],
    'mine-audit-v25-su-pom-2s': [('Сведения спрятаны внутри общей карточки ПОМ-2; разновидность не является отдельным объектом каталога.', 'ПОМ-2С сохранена отдельной карточкой. Модель POM 2S приведена отдельной страницей в полевом справочнике HALO Trust (2005).')],
    'mine-audit-v25-yu-pmr-3': [('Модель перечислена в FM 3-34.2; в базе нет отдельной карточки.', 'Обозначение PMR-3 перечислено в FM 3-34.2. Размеры приведены отдельной строкой в полевом справочнике HALO Trust (2005), стр. 54.')],
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
        data['contentVersion'] = max(data['contentVersion'], 100)
    return result

if __name__ == '__main__':
    path = ROOT / 'content/catalog.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    patches = json.loads((ROOT / 'content/reference_specs_v152.json').read_text(encoding='utf-8'))
    result = update(data, patches)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    rows = list(audit(data))
    with (ROOT / 'docs/ALL_CARDS_TTX_AUDIT.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({'added': len(result['added']), 'audited': len(rows), 'ammunition_without_specs_section': sum(r['section'] == 'AMMUNITION' and r['specs_section'] == 'no' for r in rows)}, ensure_ascii=False))
