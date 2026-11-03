#!/usr/bin/env python3
"""Add 8 owner-approved exterior reconstructions (catalog 236)."""
from __future__ import annotations
import hashlib,json
from pathlib import Path
from PIL import Image
from build_catalog import PRODUCTION_CATALOG,PRODUCTION_DATABASE,ASSETS,build
ROOT=Path(__file__).resolve().parents[1]; AOSEARCH=ROOT.parent/'aosearch'; VERSION=236; TODAY='2026-11-02'
BANK=AOSEARCH/'v236_reconstructions'; WORK=ROOT/'build/catalog236-reconstruction-batch'
ITEMS=json.loads((AOSEARCH/'v236_items.json').read_text(encoding='utf-8'))
SOURCES={
 'refubk7':('Afghanistan Ordnance ID Guide, Volume 1 (2004), публикация Bulletpicker','https://bulletpicker.com/cartridge_-115mm-heat-fs_-3ubk.html'),
 'ref545blank':('5,45-мм патроны, открытый справочный материал','https://kk-combat.ucoz.ru/proekt1/Htm_boot/m_545a.html'),
 'ref762ps':('7,62-мм патроны обр. 1943 г., открытый справочный материал','https://kk-combat.ucoz.ru/proekt1/Htm_boot/m_762a.html'),
 'ref762blank':('7,62-мм патроны обр. 1943 г., открытый справочный материал','https://kk-combat.ucoz.ru/proekt1/Htm_boot/m_762a.html'),
 'ref9pst':('9-мм пистолетные патроны, открытый справочный материал','https://kk-combat.ucoz.ru/proekt1/Htm_boot/m_9p.html'),
 'ref127blank':('12,7-мм патроны, открытый справочный материал','https://kk-combat.ucoz.ru/proekt1/Htm_boot/m_127.html'),
 'ref145blank':('14,5-мм патроны, открытый справочный материал','https://kk-combat.ucoz.ru/proekt1/Htm_boot/m_145.html')}
def main():
 WORK.mkdir(parents=True,exist_ok=True); data=json.loads(PRODUCTION_CATALOG.read_text(encoding='utf-8')); cards={c['id']:c for c in data['cards']}; entries=[]
 for item in ITEMS:
  slug=item['stem']; card=cards[item['cardId']]; title=item['title']; stem=f'reconstruction-v236-{slug}'
  if card['images']: raise RuntimeError(f'Unexpected existing image: {item["cardId"]}')
  raster=Image.open(BANK/f'{slug}.png').convert('RGB'); raster.thumbnail((1600,1600),Image.Resampling.LANCZOS)
  full_rel,thumb_rel=f'images/{stem}.webp',f'thumbs/{stem}.webp'; full,thumb=ASSETS/full_rel,ASSETS/thumb_rel
  raster.save(full,'WEBP',quality=90,method=6); miniature=raster.copy(); miniature.thumbnail((256,256),Image.Resampling.LANCZOS); miniature.save(thumb,'WEBP',quality=84,method=6)
  source_title,url=SOURCES[item['source']]
  card['images']=[{'id':stem,'localPath':full_rel,'caption':f'{title} — иллюстративная реконструкция внешнего вида по открытому источнику. Не фотография и не рабочий чертёж; маркировка и клейма не воспроизводятся.','width':raster.width,'height':raster.height,'position':0,'thumbnailPath':thumb_rel}]; card['thumbnailPath']=thumb_rel
  card['sources'].append({'id':f'source-{stem}','title':f'{title} — {source_title}; исходная иллюстрация в каталог не копировалась','url':url,'accessedAt':TODAY})
  entries.append({'cardId':item['cardId'],'imageId':stem,'fullSha256':hashlib.sha256(full.read_bytes()).hexdigest(),'thumbnailSha256':hashlib.sha256(thumb.read_bytes()).hexdigest(),'license':'Original AI-assisted illustrative reconstruction; no source image redistributed','sourceReference':url,'sourcePage':0,'status':'Approved by owner'})
 if len(entries)!=8: raise RuntimeError(f'Expected 8, got {len(entries)}')
 data['contentVersion']=data['catalogVersion']=VERSION; PRODUCTION_CATALOG.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); (ASSETS/'database/content-version.txt').write_text(f'{VERSION}\n')
 counts=build(PRODUCTION_CATALOG,PRODUCTION_DATABASE); (WORK/'reconstruction-batch-v236.json').write_text(json.dumps({'batch':'original-reconstruction-batch-v236','generatedAt':TODAY,'entries':entries,'build':counts},ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); print(json.dumps({'added':len(entries),'build':counts},ensure_ascii=False,indent=2))
if __name__=='__main__': main()
