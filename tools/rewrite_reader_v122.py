"""Apply individual narratives to an explicit catalog-151 snapshot.

All previous provenance stays byte-for-byte at the beginning of service notes.
Only three administrative table rows move to that archive; physical values,
variant qualifiers, images and medical cards remain protected.
"""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import re
from reader_122_curated import CURATED
from rewrite_reader_v121 import MEASURE, READY, split_sections, table_blocks

ROOT = Path(__file__).resolve().parents[1]
SERVICE = '\n\n## Служебные сведения'
ARCHIVED_ROWS = {
    'mine-audit-v25-de-sm-70': ['Сфера подтверждения первичной публикации'],
    'ref-v10-artillery-xm1113': ['Документированный XM1113'],
    'ref-v10-artillery-xm1128': ['Документированный XM1128'],
}

def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True).encode()).hexdigest()

def tables(text, id):
    result=[]
    for match in re.finditer(r'(?m)^\|[^\n]+(?:\n\|[^\n]+)*',text):
        lines=match[0].splitlines()
        kept=[]
        for line in lines:
            cells=[c.strip() for c in line.strip().strip('|').split('|')]
            if len(cells)==2 and cells[0] in ARCHIVED_ROWS.get(id,[]):continue
            # Bibliographic identifiers in labels are kept in the exact old article
            # archive. The value cell, including uncertainties, is never edited.
            if len(cells)==2 and cells[0] not in ('Параметр','---'):
                key=cells[0]
                key=re.sub(r' — TM 43-0001-36$','',key)
                key=re.sub(r' по (?:Bundesarchiv|CISR|WEG|HALO|NAVEODTECHDIV|BIEM|таблице TM)$','',key)
                key=re.sub(r' на первичном рисунке$','',key)
                key=re.sub(r' на первичном рисунке PDF \d+$','',key)
                key=re.sub(r' первичного рисунка PDF \d+$','',key)
                key=key.replace(' в этой таблице','').replace(' по этой строке CISR','')
                line='| '+key+' | '+cells[1]+' |'
            kept.append(line)
        if len(kept)>2:result.append('\n'.join(kept))
    return '\n\n'.join(result)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--input',type=Path,required=True)
    args=parser.parse_args()
    data=json.loads(args.input.read_text())
    if data['contentVersion']!=151:raise ValueError('Requires catalog 151')
    originals={c['id']:json.loads(json.dumps(c)) for c in data['cards']}
    assert set(CURATED)<=set(originals)
    baseline=[]
    audit=[]
    lost_quantities=[]
    for card in data['cards']:
        id=card['id']
        article,sep,notes=card['body'].partition(SERVICE)
        if id in CURATED:assert sep,id
        row=dict(id=id,identity=digest({k:v for k,v in card.items() if k not in ('body','summary')}),
                 notesHash=hashlib.sha256(notes.encode()).hexdigest(),notesLength=len(notes),
                 bodyHash=hashlib.sha256(card['body'].encode()).hexdigest(),summary=card['summary'],
                 measurements=list(dict.fromkeys(MEASURE.findall(article))),
                 tableValues=[v for t in table_blocks(article) for k,v in t],
                 archivedTableValues=[v for t in table_blocks(article) for k,v in t if k in ARCHIVED_ROWS.get(id,[])])
        baseline.append(row)
        if id not in CURATED:continue
        edit=CURATED[id]
        blocks=[]
        description_added=False
        for heading,text in split_sections(article):
            if heading=='Страна и происхождение':
                country=edit['country'] or text
                country=re.sub(r' — страна, указанная в заголовке статьи.*$','',country)
                blocks.append('## '+heading+'\n\n'+country)
            elif heading=='Описание':
                blocks.append('## Описание\n\n'+'\n\n'.join(edit['paragraphs']))
                description_added=True
            elif heading in edit['sections']:
                blocks.append('## '+heading+'\n\n'+edit['sections'][heading])
            elif heading=='При обнаружении' or heading=='Другие обозначения':
                blocks.append('## '+heading+'\n\n'+text)
            else:
                table=tables(text,id)
                if table:blocks.append('## '+heading+'\n\n'+table)
        assert description_added,id
        revised='\n\n'.join(blocks)
        missing=[v for v in row['measurements'] if v not in revised]
        # Never silently restore a generic paragraph. Missing exact quantities
        # must be reviewed and placed in the appropriate individual description.
        if missing:lost_quantities.append((id,missing))
        evidence='\n'.join(json.dumps(e,ensure_ascii=False) for e in edit['evidence'])
        archived='\n\n### Редакция 152 — индивидуальное описание\n\n'
        archived+='Проверено 2026-10-06. Предыдущая статья сохранена целиком:\n\n'+article
        if evidence:archived+='\n\nНовые подтверждения: \n'+evidence
        card['summary']=edit['paragraphs'][0]
        card['body']=revised+SERVICE+notes+archived
        assert originals[id]['body']!=card['body']
        audit.append(dict(id=id,title=card['title'],categoryId=card['categoryId'],
                          paragraphs=len(edit['paragraphs']),newEvidence=edit['evidence'],
                          previousBodyHash=row['bodyHash'],bodyHash=hashlib.sha256(card['body'].encode()).hexdigest(),
                          archivedTableValues=row['archivedTableValues']))
    if lost_quantities:raise ValueError('Visible quantities must be restored: '+repr(lost_quantities))
    data['contentVersion']=data['catalogVersion']=152
    counts=dict(collections.Counter(c['categoryId'] for c in audit))
    (ROOT/'tools/reader_151_baseline.json').write_text(json.dumps(baseline,ensure_ascii=False,indent=2)+'\n')
    (ROOT/'content/catalog.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    (ROOT/'docs/READER_152_AUDIT.json').write_text(json.dumps(dict(contentVersion=152,cards=audit,counts=counts),ensure_ascii=False,indent=2)+'\n')
    print('Individual narratives:',len(audit),counts)

if __name__=='__main__':main()
