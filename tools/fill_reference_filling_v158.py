"""Add model-specific reference filling facts without importing operating details."""
import csv
import json
import re
from fill_reference_specs_v146 import ROOT, SPEC_HEADING, audit
from fill_reference_filling_v155 import FILLING_LABEL, write_csv


def update(data, patches):
    changed = []
    assert set(patches) <= {c['id'] for c in data['cards']}
    for card in data['cards']:
        patch = patches.get(card['id'])
        if not patch:
            continue
        rows = ['| ' + name + ' | ' + value + ' |' for name, value in patch['rows']]
        present = [row in card['body'].splitlines() for row in rows]
        if all(present):
            continue
        assert not any(present), card['id']
        for old, new in patch.get('replacements', []):
            assert card['body'].count(old) == 1, (card['id'], old)
            card['body'] = card['body'].replace(old, new, 1)
        heading = SPEC_HEADING.search(card['body'])
        assert heading, card['id']
        heading_end = card['body'].index('\n', heading.end())
        table = re.match(r'\n\n(?:\|[^\n]*\n)+', card['body'][heading_end:])
        if table:
            end = heading_end + table.end()
            inserted = '\n'.join(rows) + '\n'
        else:
            # Preserve the existing reference paragraph below the new table.
            assert card['body'][heading_end:].startswith('\n\n'), card['id']
            end = heading_end + 2
            inserted = '| Параметр | Значение по источнику |\n| --- | --- |\n' + '\n'.join(rows) + '\n\n'
        card['body'] = card['body'][:end] + inserted + card['body'][end:]
        after_table = end + len(inserted)
        next_heading = re.search(r'^## ', card['body'][after_table:], re.M)
        position = after_table + next_heading.start() if next_heading else len(card['body'])
        note = 'Сведения о наполнении: ' + patch['note']
        source_line = 'Источник дополнения: ' + '; '.join(s['title'] for s in patch['sources']) + '.'
        card['body'] = card['body'][:position].rstrip() + '\n\n' + note + '\n\n' + source_line + '\n\n' + card['body'][position:]
        for source in patch['sources']:
            existing = next((s for s in card['sources'] if s['id'] == source['id']), None)
            if existing:
                assert existing == source
            else:
                card['sources'].append(source)
        changed.append(card['id'])
    if changed:
        data['contentVersion'] = max(data['contentVersion'], 106)
    return {'changed': changed}


def filling_audit(data, reviewed, prior_status):
    for card in data['cards']:
        rows = [line for line in card['body'].splitlines()
                if line.startswith('|') and FILLING_LABEL.search(line.split('|')[1])]
        status = 'checked_v158' if card['id'] in reviewed else prior_status.get(card['id'], 'not_reviewed_in_v158')
        if not status.startswith('checked_'):
            status = 'not_reviewed_in_v158'
        yield {'id': card['id'], 'title': card['title'], 'section': card['section'],
               'filling_table_rows': ' ; '.join(rows), 'review_status': status}


if __name__ == '__main__':
    path = ROOT / 'content/catalog.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    patches = json.loads((ROOT / 'content/reference_filling_v158.json').read_text(encoding='utf-8'))
    audit_path = ROOT / 'docs/ALL_CARDS_FILLING_AUDIT.csv'
    with audit_path.open(encoding='utf-8-sig', newline='') as f:
        prior_status = {row['id']: row['review_status'] for row in csv.DictReader(f)}
    result = update(data, patches)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    write_csv(ROOT / 'docs/ALL_CARDS_TTX_AUDIT.csv', audit(data))
    write_csv(audit_path, filling_audit(data, patches, prior_status))
    print(json.dumps({'changed_cards': len(result['changed']), 'content_version': data['contentVersion'], 'audited_cards': len(data['cards'])}))
