"""Apply the model-scoped v195 source review without altering unrelated cards."""
import csv
import json
from fill_reference_specs_v146 import ROOT, audit
from fill_reference_filling_v155 import write_csv
from fill_reference_filling_v189 import filling_audit


def update(data, bundle):
    patches = bundle['reviews']
    assert set(patches) <= {c['id'] for c in data['cards']}
    changed = []
    for card in data['cards']:
        patch = patches.get(card['id'])
        if patch is None:
            continue
        did_change = False
        for old, new in patch['replacements']:
            assert old != new
            if new in card['body']:
                assert card['body'].count(new) == 1, card['id']
                continue
            assert card['body'].count(old) == 1, (card['id'], old)
            card['body'] = card['body'].replace(old, new, 1)
            did_change = True
        for source in patch['sources']:
            found = [s for s in card['sources'] if s['id'] == source['id']]
            if found:
                assert found == [source], card['id']
            else:
                card['sources'].append(source)
                did_change = True
        if did_change:
            changed.append(card['id'])
    if changed:
        data['contentVersion'] = max(data['contentVersion'], 143)
    return {'changed': changed}


if __name__ == '__main__':
    path = ROOT / 'content/catalog.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    bundle = json.loads((ROOT / 'content/reference_review_v195.json').read_text(encoding='utf-8'))
    audit_path = ROOT / 'docs/ALL_CARDS_FILLING_AUDIT.csv'
    with audit_path.open(encoding='utf-8-sig', newline='') as f:
        prior = {x['id']: x['review_status'] for x in csv.DictReader(f)}
    result = update(data, bundle)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    write_csv(ROOT / 'docs/ALL_CARDS_TTX_AUDIT.csv', audit(data))
    rows = list(filling_audit(data, [], prior))
    for row in rows:
        if row['id'] in bundle['reviews']:
            row['review_status'] = 'checked_v195'
        elif not row['review_status'].startswith('checked_'):
            row['review_status'] = 'not_reviewed_in_v195'
    write_csv(audit_path, rows)
    print(json.dumps({'changed_cards': len(result['changed']), 'source_reviews': len(bundle['reviews']), 'content_version': data['contentVersion']}))
