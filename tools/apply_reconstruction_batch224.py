#!/usr/bin/env python3
"""Add 17 owner-approved reconstructions from US Army manuals (catalog 224)."""
from __future__ import annotations
import hashlib,json
from pathlib import Path
from PIL import Image
from build_catalog import PRODUCTION_CATALOG,PRODUCTION_DATABASE,ASSETS,build
ROOT=Path(__file__).resolve().parents[1];TODAY="2026-11-02";VERSION=224
BANK=ROOT.parent/"aosearch/v224_reconstructions";WORK=ROOT/"build/catalog224-reconstruction-batch"
U28="https://www.bulletpicker.com/pdf/TM-43-0001-28-1994.pdf";U36="https://www.bulletpicker.com/pdf/TM-43-0001-36.pdf"
ITEMS=[
("ordnance-v29-ga-0045","105 мм M760","01_m760",282,U28),("ordnance-v29-ga-0115","M1029","02_m1029",634,U28),
("ordnance-v29-ga-0126","M407A1","03_m407a1",594,U28),("ordnance-v29-ga-0214","120 мм M934A1","04_m934a1",518,U28),
("ordnance-v29-ga-0230","4.2-inch M329A1","05_m329a1",504,U28),("ordnance-v29-ga-0462","105 мм DM128","06_dm128",142,U28),
("ordnance-v29-ga-0474","105 мм M490","07_m490",126,U28),("ordnance-v29-ga-0476","105 мм M494","08_m494",108,U28),
("ordnance-v29-ga-0495","40 мм M813","09_m813",54,U28),("ordnance-v29-ga-0496","40 мм M822","10_m822",46,U28),
("ordnance-v29-ga-0528","90 мм M580","11_m580",84,U28),("ordnance-v29-ga-0494","40 мм M811","12_m811",48,U28),
("ordnance-v29-ga-0384","M56 mine dispensing subsystem","13_m56",28,U36),("ordnance-v29-ga-0398","M35 practice","14_m35",72,U36),
("ordnance-v29-ga-0400","M69 practice","15_m69",76,U36),("ordnance-v29-ga-0402","M8 practice","16_m8_m8a1",58,U36),
("ordnance-v29-ga-0405","M8A1 practice","17_m8a1",58,U36)]
def main():
 WORK.mkdir(parents=True,exist_ok=True);data=json.loads(PRODUCTION_CATALOG.read_text(encoding="utf-8"));cards={c["id"]:c for c in data["cards"]};entries=[]
 for card_id,title,slug,page,url in ITEMS:
  stem=f"reconstruction-v224-{slug.replace('_','-')}";card=cards[card_id]
  if any(not x["id"].startswith("reconstruction-v224-") for x in card["images"]):raise RuntimeError(f"Unexpected existing image: {card_id}")
  raster=Image.open(BANK/f"{slug}.png").convert("RGB");raster.thumbnail((1600,1600),Image.Resampling.LANCZOS)
  full_rel,thumb_rel=f"images/{stem}.webp",f"thumbs/{stem}.webp";full,thumb=ASSETS/full_rel,ASSETS/thumb_rel
  raster.save(full,"WEBP",quality=90,method=6);miniature=raster.copy();miniature.thumbnail((256,256),Image.Resampling.LANCZOS);miniature.save(thumb,"WEBP",quality=84,method=6)
  card["images"]=[{"id":stem,"localPath":full_rel,"caption":f"{title} — иллюстративная реконструкция внешнего вида по официальному пособию США, PDF-страница {page}. Не фотография и не рабочий чертёж; маркировка и клейма не воспроизводятся.","width":raster.width,"height":raster.height,"position":0,"thumbnailPath":thumb_rel}];card["thumbnailPath"]=thumb_rel
  source={"id":f"source-{stem}","title":f"{title} — официальное пособие США, PDF-страница {page}; исходная схема в каталог не копировалась","url":url,"accessedAt":TODAY};card["sources"]=[x for x in card["sources"] if not x["id"].startswith("source-reconstruction-v224-")]+[source]
  entries.append({"cardId":card_id,"imageId":stem,"fullSha256":hashlib.sha256(full.read_bytes()).hexdigest(),"thumbnailSha256":hashlib.sha256(thumb.read_bytes()).hexdigest(),"license":"Original AI-assisted illustrative reconstruction; no source image redistributed","sourceReference":url,"sourcePage":page,"status":"Approved by owner"})
 data["contentVersion"]=data["catalogVersion"]=VERSION;PRODUCTION_CATALOG.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8");(ASSETS/"database/content-version.txt").write_text(f"{VERSION}\n",encoding="utf-8")
 counts=build(PRODUCTION_CATALOG,PRODUCTION_DATABASE);(WORK/"reconstruction-batch-v224.json").write_text(json.dumps({"batch":"original-reconstruction-batch-v224","generatedAt":TODAY,"entries":entries,"build":counts},ensure_ascii=False,indent=2)+"\n",encoding="utf-8");print(json.dumps({"added":len(entries),"build":counts},ensure_ascii=False,indent=2))
if __name__=="__main__":main()
