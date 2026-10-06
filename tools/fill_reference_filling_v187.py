"""Add model-scoped large-batch filling and physical reference facts, idempotently."""
import csv
import json
from fill_reference_specs_v146 import ROOT, audit
from fill_reference_filling_v155 import FILLING_LABEL, write_csv
import re
from fill_reference_specs_v146 import SPEC_HEADING

def update_filling(data, patches):
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
        headings = list(SPEC_HEADING.finditer(card['body']))
        if not headings and patch.get('create_heading'):
            anchor = re.search(r'^## (?:Источник описания|Ограничения сведений|При обнаружении)', card['body'], re.M)
            assert anchor, card['id']
            marker = '\n' + anchor.group(0)
            assert card['body'].count(marker) == 1, card['id']
            card['body'] = card['body'].replace(marker, '\n## ТТХ\n\n' + marker, 1)
            headings = list(SPEC_HEADING.finditer(card['body']))
        index = patch.get('heading_occurrence', 0)
        assert type(index) is int and 0 <= index < len(headings), card['id']
        heading = headings[index]
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
        note = 'Уточнение справочных данных: ' + patch['note']
        source_line = 'Источник дополнения: ' + '; '.join(s['title'] for s in patch['sources']) + '.'
        card['body'] = card['body'][:position].rstrip() + '\n\n' + note + '\n\n' + source_line + '\n\n' + card['body'][position:]
        for source in patch['sources']:
            existing = next((s for s in card['sources'] if s['id'] == source['id']), None)
            if existing:
                assert existing == source
            else:
                card['sources'].append(source)
        for fix in patch.get('image_caption_corrections', []):
            image = next(im for im in card['images'] if im['id'] == fix['id'])
            assert image['caption'] == fix['old']
            image['caption'] = fix['new']
        if 'summary_correction' in patch:
            fix = patch['summary_correction']
            assert card['summary'] == fix['old']
            card['summary'] = fix['new']
        changed.append(card['id'])
    if changed:
        data['contentVersion'] = max(data['contentVersion'], 135)
    return {'changed': changed}


def update(data, bundle):
    changed=set()
    known={c['id'] for c in data['cards']}
    for key in ['filling','text_corrections','source_corrections','field_corrections']:
        assert set(bundle[key]) <= known
    for card in data['cards']:
        for field,fix in bundle['field_corrections'].get(card['id'],{}).items():
            assert field == 'countries'
            assert fix == {'old': [], 'new': ['pl']} or (card['id'] in ['ref-v10-su-m26', 'ref-v10-su-kb'] and fix == {'old': [], 'new': ['ru']})
            if card[field] == fix['new']:continue
            assert card[field] == fix['old'],card['id']
            assert all(x in {c['id'] for c in data['countries']} for x in fix['new'])
            card[field] = list(fix['new'])
            changed.add(card['id'])
        for old,new in bundle['text_corrections'].get(card['id'],[]):
            if new in card['body']:
                assert old not in card['body']
                continue
            assert card['body'].count(old)==1,card['id']
            card['body']=card['body'].replace(old,new,1)
            changed.add(card['id'])
        for fix in bundle['source_corrections'].get(card['id'],[]):
            found=[s for s in card['sources'] if s['id']==fix['id']]
            assert len(found)==1
            source=found[0]
            already = source['title'] == fix['new_title']
            if already:
                assert fix['old_title'] not in card['body']
                if 'new_url' in fix: assert source['url'] == fix['new_url']
                continue
            assert source['title'] == fix['old_title']
            if 'old_url' in fix: assert source['url'] == fix['old_url']
            if fix['old_title'] in card['body']:
                assert card['body'].count(fix['old_title']) == 1
                card['body'] = card['body'].replace(fix['old_title'], fix['new_title'], 1)
            source['title'] = fix['new_title']
            if 'new_url' in fix: source['url'] = fix['new_url']
            changed.add(card['id'])
    changed.update(update_filling(data,bundle['filling'])['changed'])
    if changed:data['contentVersion']=max(data['contentVersion'],135)
    return {'changed':[c['id'] for c in data['cards'] if c['id'] in changed]}

def filling_audit(data, reviewed, prior):
    for card in data['cards']:
        rows=[line for line in card['body'].splitlines() if line.startswith('|') and FILLING_LABEL.search(line.split('|')[1])]
        status='checked_v187' if card['id'] in reviewed else prior.get(card['id'],'not_reviewed_in_v187')
        if not status.startswith('checked_'):status='not_reviewed_in_v187'
        yield {'id':card['id'],'title':card['title'],'section':card['section'],'filling_table_rows':' ; '.join(rows),'review_status':status}

if __name__=='__main__':
    path=ROOT/'content/catalog.json'
    data=json.loads(path.read_text(encoding='utf-8'))
    bundle=json.loads((ROOT/'content/reference_filling_v187.json').read_text(encoding='utf-8'))
    audit_path=ROOT/'docs/ALL_CARDS_FILLING_AUDIT.csv'
    with audit_path.open(encoding='utf-8-sig',newline='') as f:prior={x['id']:x['review_status'] for x in csv.DictReader(f)}
    result=update(data,bundle)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    write_csv(ROOT/'docs/ALL_CARDS_TTX_AUDIT.csv',audit(data))
    write_csv(audit_path,filling_audit(data,bundle['filling'],prior))
    print(json.dumps({'changed_cards':len(result['changed']),'filling_reviews':len(bundle['filling']),'content_version':data['contentVersion'],'audited_cards':len(data['cards'])}))
