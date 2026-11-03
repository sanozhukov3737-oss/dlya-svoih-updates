#!/usr/bin/env python3
"""Add 24 owner-approved exterior reconstructions (catalog 233)."""
from __future__ import annotations
import hashlib, json
from pathlib import Path
from PIL import Image
from build_catalog import PRODUCTION_CATALOG, PRODUCTION_DATABASE, ASSETS, build
ROOT=Path(__file__).resolve().parents[1]; AOSEARCH=ROOT.parent/'aosearch'
TODAY='2026-11-02'; VERSION=233
BANK=AOSEARCH/'v233_reconstructions'; WORK=ROOT/'build/catalog233-reconstruction-batch'
ITEMS=json.loads((AOSEARCH/'v233_items.json').read_text(encoding='utf-8'))
EXCLUDED={x['stem'] for x in json.loads((AOSEARCH/'v233_excluded.json').read_text(encoding='utf-8'))}
SOURCES={
 'ks19':('КС-19, открытое пособие','https://sprotyvg7.com.ua/wp-content/uploads/2023/07/КС-19.pdf'),
 't12-ubm10-ubk8':('Описание 100-мм выстрелов, открытое дополнение','https://sprotyvg7.com.ua/'),
 'd44':('85-мм дивизионная пушка Д-44, открытое пособие','https://sprotyvg7.com.ua/wp-content/uploads/2024/01/85-мм-дивизионная-пушка-Д-44__.pdf'),
 'lviv2011':('Боєприпаси, Львів, 2011','https://sprotyvg7.com.ua/wp-content/uploads/2022/06/Боєприпаси-Лівів-2011.pdf'),
 'f57bz542':('12,7-мм патроны, открытый справочный материал','https://kk-combat.ucoz.ru/proekt1/Htm_boot/m_127.html'),
 'f127_7bz1':('12,7-мм патроны, открытый справочный материал','https://kk-combat.ucoz.ru/proekt1/Htm_boot/m_127.html'),
 'f57bzt542m':('12,7-мм патроны, открытый справочный материал','https://kk-combat.ucoz.ru/proekt1/Htm_boot/m_127.html'),
 'kalashnikov-10-16':('Калашников, открытый журнальный материал','https://www.kalashnikov.ru/medialibrary/804/10_16.pdf')
}
def main():
    WORK.mkdir(parents=True,exist_ok=True)
    data=json.loads(PRODUCTION_CATALOG.read_text(encoding='utf-8')); cards={c['id']:c for c in data['cards']}; entries=[]
    for item in ITEMS:
        slug=item['stem']
        if slug in EXCLUDED: continue
        card_id,title,page=item['cardId'],item['title'],item['page']; stem=f"reconstruction-v233-{slug.replace('_','-')}"; card=cards[card_id]
        if card['images']: raise RuntimeError(f'Unexpected existing image: {card_id}')
        raster=Image.open(BANK/f'{slug}.png').convert('RGB'); raster.thumbnail((1600,1600),Image.Resampling.LANCZOS)
        full_rel,thumb_rel=f'images/{stem}.webp',f'thumbs/{stem}.webp'; full,thumb=ASSETS/full_rel,ASSETS/thumb_rel
        raster.save(full,'WEBP',quality=90,method=6)
        miniature=raster.copy(); miniature.thumbnail((256,256),Image.Resampling.LANCZOS); miniature.save(thumb,'WEBP',quality=84,method=6)
        locator=f', PDF-страница {page}' if page else ''
        card['images']=[{'id':stem,'localPath':full_rel,'caption':f'{title} — иллюстративная реконструкция внешнего вида по открытому источнику{locator}. Не фотография и не рабочий чертёж; маркировка и клейма не воспроизводятся.','width':raster.width,'height':raster.height,'position':0,'thumbnailPath':thumb_rel}]
        card['thumbnailPath']=thumb_rel
        source_title,url=SOURCES[item['source']]
        source={'id':f'source-{stem}','title':f'{title} — {source_title}{locator}; исходная иллюстрация в каталог не копировалась','url':url,'accessedAt':TODAY}
        card['sources'].append(source)
        entries.append({'cardId':card_id,'imageId':stem,'fullSha256':hashlib.sha256(full.read_bytes()).hexdigest(),'thumbnailSha256':hashlib.sha256(thumb.read_bytes()).hexdigest(),'license':'Original AI-assisted illustrative reconstruction; no source image redistributed','sourceReference':url,'sourcePage':page,'status':'Approved by owner'})
    if len(entries)!=24: raise RuntimeError(f'Expected 24 entries, got {len(entries)}')
    data['contentVersion']=data['catalogVersion']=VERSION
    PRODUCTION_CATALOG.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (ASSETS/'database/content-version.txt').write_text(f'{VERSION}\n',encoding='utf-8')
    counts=build(PRODUCTION_CATALOG,PRODUCTION_DATABASE)
    (WORK/'reconstruction-batch-v233.json').write_text(json.dumps({'batch':'original-reconstruction-batch-v233','generatedAt':TODAY,'entries':entries,'build':counts},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'added':len(entries),'build':counts},ensure_ascii=False,indent=2))
if __name__=='__main__': main()
