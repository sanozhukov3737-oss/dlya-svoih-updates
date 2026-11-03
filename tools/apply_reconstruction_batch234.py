#!/usr/bin/env python3
"""Add 22 owner-approved exterior reconstructions (catalog 234)."""
from __future__ import annotations
import hashlib,json
from pathlib import Path
from PIL import Image
from build_catalog import PRODUCTION_CATALOG,PRODUCTION_DATABASE,ASSETS,build
ROOT=Path(__file__).resolve().parents[1]; AOSEARCH=ROOT.parent/'aosearch'; VERSION=234; TODAY='2026-11-02'
BANK=AOSEARCH/'v234_reconstructions'; WORK=ROOT/'build/catalog234-reconstruction-batch'
ITEMS=json.loads((AOSEARCH/'v234_items.json').read_text(encoding='utf-8')); EXCLUDED={x['stem'] for x in json.loads((AOSEARCH/'v234_excluded.json').read_text(encoding='utf-8'))}
SOURCES={
'ref76he':('76-мм УОФ-354М, открытая музейная публикация','https://www.lovecpokladu.cz/klub/a/76-354m-76-2x385r-20586',0),
'ref76ap':('Russian WWII 76.2 mm Cannon Ammunition, BOCN','https://www.bocn.co.uk/threads/russian-wwii-76-2-mm-cannon-ammunition.94945/',0),
'd44-236':('85-мм дивизионная пушка Д-44, открытое пособие','https://sprotyvg7.com.ua/wp-content/uploads/2024/01/85-мм-дивизионная-пушка-Д-44__.pdf',236),
'd44-237':('85-мм дивизионная пушка Д-44, открытое пособие','https://sprotyvg7.com.ua/wp-content/uploads/2024/01/85-мм-дивизионная-пушка-Д-44__.pdf',237),
'd44-238':('85-мм дивизионная пушка Д-44, открытое пособие','https://sprotyvg7.com.ua/wp-content/uploads/2024/01/85-мм-дивизионная-пушка-Д-44__.pdf',238),
'ks19-024':('КС-19, открытое пособие','https://sprotyvg7.com.ua/wp-content/uploads/2023/07/КС-19.pdf',24),
'lviv2011-183':('Боєприпаси, Львів, 2011','https://sprotyvg7.com.ua/wp-content/uploads/2022/06/Боєприпаси-Лівів-2011.pdf',183)}
def main():
 WORK.mkdir(parents=True,exist_ok=True); data=json.loads(PRODUCTION_CATALOG.read_text(encoding='utf-8')); cards={c['id']:c for c in data['cards']}; entries=[]
 for item in ITEMS:
  slug=item['stem']
  if slug in EXCLUDED: continue
  card=cards[item['cardId']]; title=item['title']; stem=f'reconstruction-v234-{slug}'
  if card['images']: raise RuntimeError(f'Unexpected existing image: {item["cardId"]}')
  raster=Image.open(BANK/f'{slug}.png').convert('RGB'); raster.thumbnail((1600,1600),Image.Resampling.LANCZOS)
  full_rel,thumb_rel=f'images/{stem}.webp',f'thumbs/{stem}.webp'; full,thumb=ASSETS/full_rel,ASSETS/thumb_rel
  raster.save(full,'WEBP',quality=90,method=6); miniature=raster.copy(); miniature.thumbnail((256,256),Image.Resampling.LANCZOS); miniature.save(thumb,'WEBP',quality=84,method=6)
  source_title,url,page=SOURCES[item['source']]; locator=f', PDF-страница {page}' if page else ''
  card['images']=[{'id':stem,'localPath':full_rel,'caption':f'{title} — иллюстративная реконструкция внешнего вида по открытому источнику{locator}. Не фотография и не рабочий чертёж; маркировка и клейма не воспроизводятся.','width':raster.width,'height':raster.height,'position':0,'thumbnailPath':thumb_rel}]; card['thumbnailPath']=thumb_rel
  card['sources'].append({'id':f'source-{stem}','title':f'{title} — {source_title}{locator}; исходная иллюстрация в каталог не копировалась','url':url,'accessedAt':TODAY})
  entries.append({'cardId':item['cardId'],'imageId':stem,'fullSha256':hashlib.sha256(full.read_bytes()).hexdigest(),'thumbnailSha256':hashlib.sha256(thumb.read_bytes()).hexdigest(),'license':'Original AI-assisted illustrative reconstruction; no source image redistributed','sourceReference':url,'sourcePage':page,'status':'Approved by owner'})
 if len(entries)!=22: raise RuntimeError(f'Expected 22, got {len(entries)}')
 data['contentVersion']=data['catalogVersion']=VERSION; PRODUCTION_CATALOG.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); (ASSETS/'database/content-version.txt').write_text(f'{VERSION}\n')
 counts=build(PRODUCTION_CATALOG,PRODUCTION_DATABASE); (WORK/'reconstruction-batch-v234.json').write_text(json.dumps({'batch':'original-reconstruction-batch-v234','generatedAt':TODAY,'entries':entries,'build':counts},ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); print(json.dumps({'added':len(entries),'build':counts},ensure_ascii=False,indent=2))
if __name__=='__main__': main()
