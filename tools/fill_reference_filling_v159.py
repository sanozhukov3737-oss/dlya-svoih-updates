"""Add reference facts and correct source dates/full-mass notes, idempotently."""
import csv
import json
from fill_reference_specs_v146 import ROOT, audit
from fill_reference_filling_v155 import FILLING_LABEL, write_csv
from fill_reference_filling_v158 import update as update_filling

def update(data, bundle):
    changed=set()
    known={c['id'] for c in data['cards']}
    for key in ['filling','text_corrections','source_corrections']:
        assert set(bundle[key]) <= known
    for card in data['cards']:
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
            if source['title']==fix['new_title']:
                assert fix['old_title'] not in card['body']
                assert fix['new_title'] in card['body']
                continue
            assert source['title']==fix['old_title']
            assert card['body'].count(fix['old_title'])==1
            source['title']=fix['new_title']
            card['body']=card['body'].replace(fix['old_title'],fix['new_title'],1)
            changed.add(card['id'])
    changed.update(update_filling(data,bundle['filling'])['changed'])
    if changed:data['contentVersion']=max(data['contentVersion'],107)
    return {'changed':[c['id'] for c in data['cards'] if c['id'] in changed]}

def filling_audit(data, reviewed, prior):
    for card in data['cards']:
        rows=[line for line in card['body'].splitlines() if line.startswith('|') and FILLING_LABEL.search(line.split('|')[1])]
        status='checked_v159' if card['id'] in reviewed else prior.get(card['id'],'not_reviewed_in_v159')
        if not status.startswith('checked_'):status='not_reviewed_in_v159'
        yield {'id':card['id'],'title':card['title'],'section':card['section'],'filling_table_rows':' ; '.join(rows),'review_status':status}

if __name__=='__main__':
    path=ROOT/'content/catalog.json'
    data=json.loads(path.read_text(encoding='utf-8'))
    bundle=json.loads((ROOT/'content/reference_filling_v159.json').read_text(encoding='utf-8'))
    audit_path=ROOT/'docs/ALL_CARDS_FILLING_AUDIT.csv'
    with audit_path.open(encoding='utf-8-sig',newline='') as f:prior={x['id']:x['review_status'] for x in csv.DictReader(f)}
    result=update(data,bundle)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    write_csv(ROOT/'docs/ALL_CARDS_TTX_AUDIT.csv',audit(data))
    write_csv(audit_path,filling_audit(data,bundle['filling'],prior))
    print(json.dumps({'changed_cards':len(result['changed']),'filling_reviews':len(bundle['filling']),'content_version':data['contentVersion'],'audited_cards':len(data['cards'])}))
