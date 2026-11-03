#!/usr/bin/env python3
"""Add four approved reconstructions and correct the BPM/VZD-1M mapping (catalog 222)."""
from __future__ import annotations
import hashlib,json
from pathlib import Path
from PIL import Image
from build_catalog import PRODUCTION_CATALOG,PRODUCTION_DATABASE,ASSETS,build
ROOT=Path(__file__).resolve().parents[1]; TODAY="2026-11-02"; VERSION=222
BANK=ROOT.parent/"aosearch/v222_reconstructions"; WORK=ROOT/"build/catalog222-reconstruction-batch"
URL="https://sprotyvg7.com.ua/wp-content/uploads/2023/12/Katalog_Sredstva_inzhenernogo_vooruzhenia_Kniga_1.pdf"
ITEMS=[("pdf198-school-mib-engineering","МИБ",299,"mib"),("pdf198-4-7657025b7ae9","ПОБ",301,"pob"),("pdf198-4-9259951d9222","СРМ",311,"srm"),("pdf198-4-91bb41b8bbaf","ЯРМ",313,"yarm"),("pdf198-4-bdd8d7d19f1f","БПМ",337,"bpm")]
def main():
 WORK.mkdir(parents=True,exist_ok=True); data=json.loads(PRODUCTION_CATALOG.read_text(encoding="utf-8")); cards={c["id"]:c for c in data["cards"]}
 wrong=cards["pdf198-4-dbff41ab0687"]; wrong["images"]=[x for x in wrong["images"] if x["id"]!="reconstruction-v219-su-vzd1m"]; wrong["sources"]=[x for x in wrong["sources"] if x["id"]!="source-reconstruction-v219-su-vzd1m"]; wrong["thumbnailPath"]=wrong["images"][0]["thumbnailPath"] if wrong["images"] else None
 entries=[]
 for card_id,title,page,slug in ITEMS:
  stem=f"reconstruction-v222-su-{slug}"; card=cards[card_id]; card["images"]=[x for x in card["images"] if x["id"]!=stem]
  raster=Image.open(BANK/f"p{page}.png").convert("RGB"); raster.thumbnail((1600,1600),Image.Resampling.LANCZOS)
  full_rel,thumb_rel=f"images/{stem}.webp",f"thumbs/{stem}.webp"; full,thumb=ASSETS/full_rel,ASSETS/thumb_rel
  raster.save(full,"WEBP",quality=90,method=6); miniature=raster.copy(); miniature.thumbnail((256,256),Image.Resampling.LANCZOS); miniature.save(thumb,"WEBP",quality=84,method=6)
  card["images"].append({"id":stem,"localPath":full_rel,"caption":f"{title} — иллюстративная реконструкция внешнего вида по фотографии оригинального экземпляра в каталоге средств инженерного вооружения, PDF-страница {page}. Не фотография и не рабочий чертёж; маркировка и клейма не воспроизводятся.","width":raster.width,"height":raster.height,"position":max((x["position"] for x in card["images"]),default=-1)+1,"thumbnailPath":thumb_rel})
  card["images"].sort(key=lambda x:(x["position"],x["id"])); card["thumbnailPath"]=card["images"][0]["thumbnailPath"]
  source={"id":f"source-{stem}","title":f"{title} — фотография оригинального экземпляра на PDF-странице {page}; использована для проверки внешней формы, исходное изображение в каталог не копировалось","url":URL,"accessedAt":TODAY}; card["sources"]=[x for x in card["sources"] if x["id"]!=source["id"]]+[source]
  entries.append({"cardId":card_id,"imageId":stem,"fullSha256":hashlib.sha256(full.read_bytes()).hexdigest(),"thumbnailSha256":hashlib.sha256(thumb.read_bytes()).hexdigest(),"license":"Original AI-assisted illustrative reconstruction; no source image redistributed","sourceReference":URL,"sourcePage":page,"status":"Approved by owner"})
 data["contentVersion"]=data["catalogVersion"]=VERSION; PRODUCTION_CATALOG.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"); (ASSETS/"database/content-version.txt").write_text(f"{VERSION}\n",encoding="utf-8")
 counts=build(PRODUCTION_CATALOG,PRODUCTION_DATABASE); (WORK/"reconstruction-batch-v222.json").write_text(json.dumps({"batch":"original-reconstruction-batch-v222","generatedAt":TODAY,"entries":entries,"removedIncorrectImage":{"cardId":"pdf198-4-dbff41ab0687","imageId":"reconstruction-v219-su-vzd1m"},"build":counts},ensure_ascii=False,indent=2)+"\n",encoding="utf-8"); print(json.dumps({"added":len(entries),"build":counts},ensure_ascii=False,indent=2))
if __name__=="__main__": main()
