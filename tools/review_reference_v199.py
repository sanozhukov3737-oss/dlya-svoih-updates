"""Apply partial source qualifications while preserving completion status."""
import json
from fill_reference_specs_v146 import ROOT, audit
from fill_reference_filling_v155 import write_csv

def update(data, bundle):
    changed = []
    assert set(bundle['reviews']) <= {c['id'] for c in data['cards']}
    for card in data['cards']:
        patch = bundle['reviews'].get(card['id'])
        if patch is None:
            continue
        did_change = False
        for old, new in patch['replacements']:
            assert old != new
            if new in card['body']:
                assert card['body'].count(new) == 1
                continue
            assert card['body'].count(old) == 1, card['id']
            card['body'] = card['body'].replace(old, new, 1)
            did_change = True
        for field, (old, new) in patch.get('field_replacements', {}).items():
            assert card[field] in (old, new), (card['id'], field)
            if card[field] == old:
                card[field] = new
                did_change = True
        for source in patch['sources']:
            found = [s for s in card['sources'] if s['id'] == source['id']]
            if found:
                assert found == [source]
            else:
                card['sources'].append(source)
                did_change = True
        if did_change:
            changed.append(card['id'])
    if changed:
        data['contentVersion'] = max(data['contentVersion'], 146)
    return {'changed': changed}

if __name__ == '__main__':
    path = ROOT / 'content/catalog.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    bundle = json.loads((ROOT / 'content/reference_review_v199.json').read_text(encoding='utf-8'))
    result = update(data, bundle)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    write_csv(ROOT / 'docs/ALL_CARDS_TTX_AUDIT.csv', audit(data))
    print(json.dumps({'source_qualified': len(result['changed']), 'closed': 0, 'remaining': 37, 'content_version': data['contentVersion']}))
