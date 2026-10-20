"""Apply reviewed physical data from the next primary-source batch."""
import csv
import json
from fill_reference_specs_v146 import ROOT, apply, audit

CORRECTIONS = {'mine-audit-v25-ru-mdm-1-mod-1': [('Отдельная серийная модель отсутствует; не путать с болгарскими MDM-5/6/7/8 в разделе специальных мин.', 'МДМ-1 мод. 1 подтверждена отдельной колонкой в экспортном каталоге Рособоронэкспорта. Обозначение не смешано с болгарскими MDM-5/6/7/8.')], 'mine-audit-v25-ru-mdm-2-mod-1': [('Отдельная серийная модель отсутствует; не путать с болгарскими MDM-5/6/7/8 в разделе специальных мин.', 'МДМ-2 мод. 1 подтверждена отдельной колонкой в экспортном каталоге Рособоронэкспорта. Обозначение не смешано с болгарскими MDM-5/6/7/8.')], 'mine-audit-v25-ru-mdm-3-mod-1': [('Отдельная серийная модель отсутствует; не путать с болгарскими MDM-5/6/7/8 в разделе специальных мин.', 'МДМ-3 мод. 1 подтверждена отдельной колонкой в экспортном каталоге Рособоронэкспорта. Обозначение не смешано с болгарскими MDM-5/6/7/8.')]}

def update(data, patches):
    result = apply(data, patches)
    for card in data['cards']:
        if card['id'] not in result['added']:
            continue
        for old, new in CORRECTIONS.get(card['id'], []):
            assert old in card['body'], (card['id'], old)
            card['body'] = card['body'].replace(old, new)
    for card in data['cards']:
        if card['id'] in result['added'] and patches[card['id']].get('extraSource'):
            card['sources'].append(patches[card['id']]['extraSource'])
    corrected = []
    for card in data['cards']:
        if card['id'] != 'mine-audit-v25-de-riegelmine-44':
            continue
        old = 'Серийная модель Второй мировой отсутствует в историческом разделе.'
        if old in card['body']:
            card['body'] = card['body'].replace(old, 'В TM 5-223C (1952), стр. 89, Riegelmine 44 описана как экспериментальная модель. Серийное производство в этом источнике не подтверждено. Размеры и полная масса конкретной Riegelmine 44 в выбранном разделе не приведены.')
            card['sources'].append({'id': 'mine-audit-v25-de-riegelmine-44-status-v153', 'title': 'US Army — TM 5-223C (1952), стр. 89, Bar Mine 44 (Riegelmine 44)', 'url': 'https://bulletpicker.com/pdf/TM-5-223C.pdf', 'accessedAt': '2026-10-04'})
            corrected.append(card['id'])
    result['text_corrections'] = corrected
    if result['added'] or result['existing_tables_exposed'] or corrected:
        data['contentVersion'] = max(data['contentVersion'], 101)
    return result

if __name__ == '__main__':
    path = ROOT / 'content/catalog.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    patches = json.loads((ROOT / 'content/reference_specs_v153.json').read_text(encoding='utf-8'))
    result = update(data, patches)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    rows = list(audit(data))
    with (ROOT / 'docs/ALL_CARDS_TTX_AUDIT.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({'added': len(result['added']), 'audited': len(rows), 'ammunition_without_specs_section': sum(r['section'] == 'AMMUNITION' and r['specs_section'] == 'no' for r in rows)}, ensure_ascii=False))
