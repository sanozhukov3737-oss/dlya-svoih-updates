#!/usr/bin/env python3
"""Add 10 owner-approved exterior reconstructions (catalog 235)."""
from __future__ import annotations
import hashlib,json
from pathlib import Path
from PIL import Image
from build_catalog import PRODUCTION_CATALOG,PRODUCTION_DATABASE,ASSETS,build
ROOT=Path(__file__).resolve().parents[1]; AOSEARCH=ROOT.parent/'aosearch'; VERSION=235; TODAY='2026-11-02'
BANK=AOSEARCH/'v235_reconstructions'; WORK=ROOT/'build/catalog235-reconstruction-batch'
ITEMS=json.loads((AOSEARCH/'v235_items.json').read_text(encoding='utf-8')); EXCLUDED={x['stem'] for x in json.loads((AOSEARCH/'v235_excluded.json').read_text(encoding='utf-8'))}
SOURCES={
 'ref115of':('115-мм выстрелы гладкоствольной танковой пушки У-5ТС, открытая справочная публикация','https://btvt.narod.ru/4/t62weapon.htm'),
 'ref115ubm4':('115-мм выстрелы гладкоствольной танковой пушки У-5ТС, открытая справочная публикация','https://btvt.narod.ru/4/t62weapon.htm'),
 'ref115ubm5':('115-мм выстрелы гладкоствольной танковой пушки У-5ТС, открытая справочная публикация','https://btvt.narod.ru/4/t62weapon.htm'),
 'ref115ubm9':('115-мм выстрелы гладкоствольной танковой пушки У-5ТС, открытая справочная публикация','https://btvt.narod.ru/4/t62weapon.htm'),
 'ref115ubk3':('115-мм выстрелы гладкоствольной танковой пушки У-5ТС, открытая справочная публикация','https://btvt.narod.ru/4/t62weapon.htm'),
 'ref115ubk3m':('115-мм выстрелы гладкоствольной танковой пушки У-5ТС, открытая справочная публикация','https://btvt.narod.ru/4/t62weapon.htm')}
def main():
 WORK.mkdir(parents=True,exist_ok=True); data=json.loads(PRODUCTION_CATALOG.read_text(encoding='utf-8')); cards={c['id']:c for c in data['cards']}; entries=[]
 for item in ITEMS:
  slug=item['stem']
  if slug in EXCLUDED: continue
  card=cards[item['cardId']]; title=item['title']; stem=f'reconstruction-v235-{slug}'
  if card['images']: raise RuntimeError(f'Unexpected existing image: {item["cardId"]}')
  raster=Image.open(BANK/f'{slug}.png').convert('RGB'); raster.thumbnail((1600,1600),Image.Resampling.LANCZOS)
  full_rel,thumb_rel=f'images/{stem}.webp',f'thumbs/{stem}.webp'; full,thumb=ASSETS/full_rel,ASSETS/thumb_rel
  raster.save(full,'WEBP',quality=90,method=6); miniature=raster.copy(); miniature.thumbnail((256,256),Image.Resampling.LANCZOS); miniature.save(thumb,'WEBP',quality=84,method=6)
  source_title,url=SOURCES[item['source']]
  card['images']=[{'id':stem,'localPath':full_rel,'caption':f'{title} — иллюстративная реконструкция внешнего вида по открытому источнику. Не фотография и не рабочий чертёж; маркировка и клейма не воспроизводятся.','width':raster.width,'height':raster.height,'position':0,'thumbnailPath':thumb_rel}]; card['thumbnailPath']=thumb_rel
  card['sources'].append({'id':f'source-{stem}','title':f'{title} — {source_title}; исходная иллюстрация в каталог не копировалась','url':url,'accessedAt':TODAY})
  entries.append({'cardId':item['cardId'],'imageId':stem,'fullSha256':hashlib.sha256(full.read_bytes()).hexdigest(),'thumbnailSha256':hashlib.sha256(thumb.read_bytes()).hexdigest(),'license':'Original AI-assisted illustrative reconstruction; no source image redistributed','sourceReference':url,'sourcePage':0,'status':'Approved by owner'})
 if len(entries)!=10: raise RuntimeError(f'Expected 10, got {len(entries)}')
 data['contentVersion']=data['catalogVersion']=VERSION; PRODUCTION_CATALOG.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); (ASSETS/'database/content-version.txt').write_text(f'{VERSION}\n')
 counts=build(PRODUCTION_CATALOG,PRODUCTION_DATABASE); (WORK/'reconstruction-batch-v235.json').write_text(json.dumps({'batch':'original-reconstruction-batch-v235','generatedAt':TODAY,'entries':entries,'build':counts},ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); print(json.dumps({'added':len(entries),'build':counts},ensure_ascii=False,indent=2))
if __name__=='__main__': main()
