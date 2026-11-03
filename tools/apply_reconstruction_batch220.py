#!/usr/bin/env python3
"""Add owner-approved reconstructions to seven existing cards (catalog 220)."""
from __future__ import annotations
import hashlib, json
from pathlib import Path
from PIL import Image
from build_catalog import PRODUCTION_CATALOG, PRODUCTION_DATABASE, ASSETS, build
ROOT=Path(__file__).resolve().parents[1]
TODAY="2026-11-02"; TARGET_VERSION=220
BANK=ROOT.parent/"aosearch/v220_reconstructions"
WORK=ROOT/"build/catalog220-reconstruction-batch"
SOURCE_URL="https://sprotyvg7.com.ua/wp-content/uploads/2023/12/Katalog_Sredstva_inzhenernogo_vooruzhenia_Kniga_1.pdf"
ITEMS=[
("pdf198-4-bb98238837fb","МПМ-Э","p345.png","reconstruction-v220-su-mpme",345),
("mine-audit-v26-su-ms-3","МС-3","p347.png","reconstruction-v220-su-ms3",347),
("ordnance-v27-ms-4","МС-4","p349.png","reconstruction-v220-su-ms4",349),
("mine-audit-v26-su-ml-7","МЛ-7","p351.png","reconstruction-v220-su-ml7",351),
("mine-audit-v26-su-ml-8","МЛ-8","p353.png","reconstruction-v220-su-ml8",353),
("pdf198-4-d726f05e02f8","СМ","p357.png","reconstruction-v220-su-sm",357),
("pdf198-4-1c19dbe4b818","МЗД-21","p335.png","reconstruction-v220-su-mzd21",335),
]
def main():
 WORK.mkdir(parents=True,exist_ok=True)
 data=json.loads(PRODUCTION_CATALOG.read_text(encoding="utf-8"))
 if data["contentVersion"] not in (TARGET_VERSION-1,TARGET_VERSION): raise RuntimeError("Unexpected catalog version")
 cards={c["id"]:c for c in data["cards"]}; entries=[]
 for card_id,title,filename,stem,page in ITEMS:
  card=cards[card_id]; card["images"]=[x for x in card["images"] if x["id"]!=stem]
  raster=Image.open(BANK/filename).convert("RGB"); raster.thumbnail((1600,1600),Image.Resampling.LANCZOS)
  full_rel,thumb_rel=f"images/{stem}.webp",f"thumbs/{stem}.webp"; full,thumb=ASSETS/full_rel,ASSETS/thumb_rel
  raster.save(full,"WEBP",quality=90,method=6); miniature=raster.copy(); miniature.thumbnail((256,256),Image.Resampling.LANCZOS); miniature.save(thumb,"WEBP",quality=84,method=6)
  card["images"].append({"id":stem,"localPath":full_rel,"caption":f"{title} — иллюстративная реконструкция внешнего вида по фотографии оригинального экземпляра в каталоге средств инженерного вооружения, PDF-страница {page}. Не фотография и не рабочий чертёж; маркировка и клейма не воспроизводятся.","width":raster.width,"height":raster.height,"position":max((x["position"] for x in card["images"]),default=-1)+1,"thumbnailPath":thumb_rel})
  card["images"].sort(key=lambda x:(x["position"],x["id"])); card["thumbnailPath"]=card["images"][0]["thumbnailPath"]
  source={"id":f"source-{stem}","title":f"{title} — фотография оригинального экземпляра на PDF-странице {page}; использована для проверки внешней формы, исходное изображение в каталог не копировалось","url":SOURCE_URL,"accessedAt":TODAY}
  card["sources"]=[x for x in card["sources"] if x["id"]!=source["id"]]+[source]
  entries.append({"cardId":card_id,"imageId":stem,"fullSha256":hashlib.sha256(full.read_bytes()).hexdigest(),"thumbnailSha256":hashlib.sha256(thumb.read_bytes()).hexdigest(),"license":"Original AI-assisted illustrative reconstruction; no source image redistributed","sourceReference":SOURCE_URL,"sourcePage":page,"status":"Approved by owner"})
 data["contentVersion"]=data["catalogVersion"]=TARGET_VERSION
 PRODUCTION_CATALOG.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 (ASSETS/"database/content-version.txt").write_text(f"{TARGET_VERSION}\n",encoding="utf-8")
 counts=build(PRODUCTION_CATALOG,PRODUCTION_DATABASE)
 (WORK/"reconstruction-batch-v220.json").write_text(json.dumps({"batch":"original-reconstruction-batch-v220","generatedAt":TODAY,"entries":entries,"build":counts},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 print(json.dumps({"updatedCards":len(entries),"build":counts},ensure_ascii=False,indent=2))
if __name__=="__main__": main()
