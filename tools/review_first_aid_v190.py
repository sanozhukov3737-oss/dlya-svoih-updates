"""Apply bounded first-aid prose corrections and source records idempotently."""
import csv,json
from fill_reference_specs_v146 import ROOT,audit
from fill_reference_filling_v155 import write_csv
from fill_reference_filling_v189 import filling_audit

def update(data,bundle):
    patches=bundle['medical_reviews']
    assert set(patches)<={c['id'] for c in data['cards']}
    changed=[]
    for card in data['cards']:
        patch=patches.get(card['id'])
        if patch is None:continue
        assert card['section']=='MEDICINE'
        did_change=False
        for old,new in patch['replacements']:
            if new in card['body']:
                # A new sentence may intentionally include the previous sentence.
                assert card['body'].count(new)==1,card['id']
                continue
            assert card['body'].count(old)==1,(card['id'],old)
            card['body']=card['body'].replace(old,new,1);did_change=True
        for source in patch['sources']:
            existing=next((s for s in card['sources'] if s['id']==source['id']),None)
            if existing is not None:assert existing==source
            else:card['sources'].append(source);did_change=True
        if did_change:changed.append(card['id'])
    if changed:data['contentVersion']=max(data['contentVersion'],138)
    return {'changed':changed}

if __name__=='__main__':
    path=ROOT/'content/catalog.json';data=json.loads(path.read_text())
    bundle=json.loads((ROOT/'content/first_aid_review_v190.json').read_text())
    ap=ROOT/'docs/ALL_CARDS_FILLING_AUDIT.csv'
    with ap.open(encoding='utf-8-sig',newline='') as f:prior={x['id']:x['review_status'] for x in csv.DictReader(f)}
    result=update(data,bundle)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    write_csv(ROOT/'docs/ALL_CARDS_TTX_AUDIT.csv',audit(data))
    rows=list(filling_audit(data,[],prior))
    for row in rows:
        if row['id'] in bundle['medical_reviews']:row['review_status']='checked_medical_v190'
        elif not row['review_status'].startswith('checked_'):row['review_status']='not_reviewed_in_v190'
    write_csv(ap,rows)
    print(json.dumps({'changed_cards':len(result['changed']),'medical_source_reviews':len(bundle['medical_reviews']),'content_version':data['contentVersion']}))
