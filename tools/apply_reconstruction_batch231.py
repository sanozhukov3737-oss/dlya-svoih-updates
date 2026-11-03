#!/usr/bin/env python3
"""Add two owner-approved exterior reconstructions (catalog 231)."""
from __future__ import annotations
import hashlib, json
from pathlib import Path
from PIL import Image
from build_catalog import PRODUCTION_CATALOG, PRODUCTION_DATABASE, ASSETS, build
ROOT=Path(__file__).resolve().parents[1]; AOSEARCH=ROOT.parent/'aosearch'
TODAY='2026-11-02'; VERSION=231
BANK=AOSEARCH/'v231_reconstructions'; WORK=ROOT/'build/catalog231-reconstruction-batch'
ARDEC='https://www.bulletpicker.com/pdf/ARDEC-Circular-70-1.pdf'
ITEMS=json.loads((AOSEARCH/'v231_items.json').read_text(encoding='utf-8'))
EXCLUDED={x['stem'] for x in json.loads((AOSEARCH/'v231_excluded.json').read_text(encoding='utf-8'))}
def main():
    WORK.mkdir(parents=True,exist_ok=True)
    data=json.loads(PRODUCTION_CATALOG.read_text(encoding='utf-8')); cards={c['id']:c for c in data['cards']}; entries=[]
    for item in ITEMS:
        slug=item['stem']
        if slug in EXCLUDED: continue
        card_id,title,page=item['cardId'],item['title'],item['page']; stem=f"reconstruction-v231-{slug.replace('_','-')}"; card=cards[card_id]
        if card['images']: raise RuntimeError(f'Unexpected existing image: {card_id}')
        raster=Image.open(BANK/f'{slug}.png').convert('RGB'); raster.thumbnail((1600,1600),Image.Resampling.LANCZOS)
        full_rel,thumb_rel=f'images/{stem}.webp',f'thumbs/{stem}.webp'; full,thumb=ASSETS/full_rel,ASSETS/thumb_rel
        raster.save(full,'WEBP',quality=90,method=6)
        miniature=raster.copy(); miniature.thumbnail((256,256),Image.Resampling.LANCZOS); miniature.save(thumb,'WEBP',quality=84,method=6)
        card['images']=[{'id':stem,'localPath':full_rel,'caption':f'{title} — иллюстративная реконструкция внешнего вида по открытому пособию, PDF-страница {page}. Не фотография и не рабочий чертёж; маркировка и клейма не воспроизводятся.','width':raster.width,'height':raster.height,'position':0,'thumbnailPath':thumb_rel}]
        card['thumbnailPath']=thumb_rel
        source={'id':f'source-{stem}','title':f'{title} — U.S. Army ARDEC Circular 70-1, PDF-страница {page}; исходная иллюстрация в каталог не копировалась','url':ARDEC,'accessedAt':TODAY}
        card['sources'].append(source)
        entries.append({'cardId':card_id,'imageId':stem,'fullSha256':hashlib.sha256(full.read_bytes()).hexdigest(),'thumbnailSha256':hashlib.sha256(thumb.read_bytes()).hexdigest(),'license':'Original AI-assisted illustrative reconstruction; no source image redistributed','sourceReference':ARDEC,'sourcePage':page,'status':'Approved by owner'})
    if len(entries)!=2: raise RuntimeError(f'Expected 2 entries, got {len(entries)}')
    data['contentVersion']=data['catalogVersion']=VERSION
    PRODUCTION_CATALOG.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (ASSETS/'database/content-version.txt').write_text(f'{VERSION}\n',encoding='utf-8')
    counts=build(PRODUCTION_CATALOG,PRODUCTION_DATABASE)
    (WORK/'reconstruction-batch-v231.json').write_text(json.dumps({'batch':'original-reconstruction-batch-v231','generatedAt':TODAY,'entries':entries,'build':counts},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'added':len(entries),'build':counts},ensure_ascii=False,indent=2))
if __name__=='__main__': main()
