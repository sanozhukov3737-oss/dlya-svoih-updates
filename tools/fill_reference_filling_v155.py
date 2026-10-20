"""Add sourced filling fields to existing TTX tables, keeping quantities distinct."""
import csv
import json
import re
from fill_reference_specs_v146 import ROOT, audit

FILLING_LABEL = re.compile(r'ВВ|взрывчат|наполн|снаряжен|пиротехническ|осветительн|NEQ|тротилов.*экв', re.I)

def filling_audit(data, reviewed):
    for card in data['cards']:
        rows = []
        for line in card['body'].splitlines():
            if line.startswith('|') and FILLING_LABEL.search(line.split('|')[1]):
                rows.append(line)
        yield {'id': card['id'], 'title': card['title'], 'section': card['section'],
               'filling_table_rows': ' ; '.join(rows),
               'review_status': 'checked_v155' if card['id'] in reviewed else 'not_reviewed_in_v155'}

def update(data, patches):
    changed = []
    known = {card['id'] for card in data['cards']}
    assert set(patches) <= known
    for card in data['cards']:
        patch = patches.get(card['id'])
        if not patch:
            continue
        rows = ['| '+name+' | '+value+' |' for name, value in patch['rows']]
        present = [row in card['body'].splitlines() for row in rows]
        if all(present):
            continue
        assert not any(present), card['id']
        match = re.search(r'^## ТТХ\n\n(?:\|[^\n]*\n)+', card['body'], re.M)
        assert match, card['id']
        card['body'] = card['body'][:match.end()] + '\n'.join(rows) + '\n' + card['body'][match.end():]
        next_heading = re.search(r'^## ', card['body'][match.end()+len('\n'.join(rows))+1:], re.M)
        note_position = match.end()+len('\n'.join(rows))+1 + next_heading.start() if next_heading else len(card['body'])
        note = 'Сведения о наполнении: '+patch['note']+'\n\n'
        card['body'] = card['body'][:note_position].rstrip()+'\n\n'+note+card['body'][note_position:]
        for source in patch['sources']:
            existing = next((s for s in card['sources'] if s['id'] == source['id']), None)
            if existing:
                assert existing == source
            else:
                card['sources'].append(source)
        if card['id'] == 'mine-audit-v25-de-topfmine-4531':
            card['body'] = card['body'].replace('Серийная модель Второй мировой отсутствует в историческом разделе.', 'Topfmine A подтверждена в TM 9-1985-2 и TM 5-223C. Характеристики варианта A и иллюстрация B4531 в этой карточке различаются по обозначению варианта.')
        changed.append(card['id'])
    if changed:
        data['contentVersion'] = max(data['contentVersion'], 103)
    return {'changed': changed}

def write_csv(path, rows):
    rows = list(rows)
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)

if __name__ == '__main__':
    path = ROOT/'content/catalog.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    patches = json.loads((ROOT/'content/reference_filling_v155.json').read_text(encoding='utf-8'))
    result = update(data, patches)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    write_csv(ROOT/'docs/ALL_CARDS_TTX_AUDIT.csv', audit(data))
    write_csv(ROOT/'docs/ALL_CARDS_FILLING_AUDIT.csv', filling_audit(data, patches))
    print(json.dumps({'changed_cards': len(result['changed']), 'content_version': data['contentVersion'], 'audited_cards': len(data['cards'])}))
