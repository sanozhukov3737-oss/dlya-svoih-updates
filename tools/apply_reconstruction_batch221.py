#!/usr/bin/env python3
"""Add owner-approved reconstructions to existing cards (catalog 221)."""
from __future__ import annotations
import hashlib,json
from pathlib import Path
from PIL import Image
from build_catalog import PRODUCTION_CATALOG,PRODUCTION_DATABASE,ASSETS,build
ROOT=Path(__file__).resolve().parents[1]; TODAY="2026-11-02"; TARGET_VERSION=221
BANK=ROOT.parent/"aosearch/v221_reconstructions"; WORK=ROOT/"build/catalog221-reconstruction-batch"
SOURCE_URL="https://sprotyvg7.com.ua/wp-content/uploads/2023/12/Katalog_Sredstva_inzhenernogo_vooruzhenia_Kniga_1.pdf"
ITEMS=[
("pdf198-4-1d69cee8dd2b","СЗ-1Э",207,"sz1e"),("pdf198-4-035dae985104","СЗ-4П",211,"sz4p"),
("ordnance-v27-sz-6","СЗ-6",213,"sz6"),("pdf198-4-cd7cdaec5a07","КФЗ",217,"kfz"),
("ordnance-v27-kz-6","КЗ-6",223,"kz6"),("pdf198-4-4d7011500e24","КЗУ",227,"kzu"),
("ordnance-v27-oz-1","ОЗ-1",237,"oz1"),("pdf198-4-25ff6389505a","КФЗ-Т",239,"kfzt"),
("pdf198-4-a17653d614a3","ВУЗ-8",245,"vuz8"),("pdf198-4-7cbd2676b091","БКМ-6",247,"bkm6"),
("ref-v9-edp","ЭДП / ЭДП-р",253,"edp"),("ref-v11-oshp","ОШП",255,"oshp"),
("ref-v9-ztp","ЗТП",259,"ztp"),("ordnance-v27-md-5m","МД-5М",261,"md5m"),
("ref-v8-tm-57","ТМ-57",263,"tm57"),("mine-audit-v25-su-tm-83","ТМ-83",269,"tm83"),
("ref-v10-ru-tm89","ТМ-89",271,"tm89"),("ref-v9-su-tmk2","ТМК-2",273,"tmk2"),
("ref-v8-ptm-4","ПТМ-4",277,"ptm4"),("eng-pmn-2","ПМН-2",279,"pmn2"),
("ref-v8-pmn-4","ПМН-4",281,"pmn4"),("ref-v8-pomz-2m","ПОМЗ-2М",283,"pomz2m"),
("eng-ozm-72","ОЗМ-72",285,"ozm72"),("eng-mon-50","МОН-50",287,"mon50"),
("ref-v8-mon-90","МОН-90",289,"mon90"),("ref-v8-mon-100","МОН-100",291,"mon100"),
("ref-v8-mon-200","МОН-200",293,"mon200"),("ref-v8-pdm-1m","ПДМ-1М",303,"pdm1m"),
("pdf198-4-9589da4a2982","МЗУ-2",321,"mzu2")]
def main():
 WORK.mkdir(parents=True,exist_ok=True); data=json.loads(PRODUCTION_CATALOG.read_text(encoding="utf-8"))
 if data["contentVersion"] not in (TARGET_VERSION-1,TARGET_VERSION): raise RuntimeError("Unexpected catalog version")
 cards={c["id"]:c for c in data["cards"]}; entries=[]
 for card_id,title,page,slug in ITEMS:
  stem=f"reconstruction-v221-su-{slug}"; card=cards[card_id]; card["images"]=[x for x in card["images"] if x["id"]!=stem]
  raster=Image.open(BANK/f"p{page}.png").convert("RGB"); raster.thumbnail((1600,1600),Image.Resampling.LANCZOS)
  full_rel,thumb_rel=f"images/{stem}.webp",f"thumbs/{stem}.webp"; full,thumb=ASSETS/full_rel,ASSETS/thumb_rel
  raster.save(full,"WEBP",quality=90,method=6); miniature=raster.copy(); miniature.thumbnail((256,256),Image.Resampling.LANCZOS); miniature.save(thumb,"WEBP",quality=84,method=6)
  card["images"].append({"id":stem,"localPath":full_rel,"caption":f"{title} — иллюстративная реконструкция внешнего вида по фотографии оригинального экземпляра в каталоге средств инженерного вооружения, PDF-страница {page}. Не фотография и не рабочий чертёж; маркировка и клейма не воспроизводятся.","width":raster.width,"height":raster.height,"position":max((x["position"] for x in card["images"]),default=-1)+1,"thumbnailPath":thumb_rel})
  card["images"].sort(key=lambda x:(x["position"],x["id"])); card["thumbnailPath"]=card["images"][0]["thumbnailPath"]
  source={"id":f"source-{stem}","title":f"{title} — фотография оригинального экземпляра на PDF-странице {page}; использована для проверки внешней формы, исходное изображение в каталог не копировалось","url":SOURCE_URL,"accessedAt":TODAY}
  card["sources"]=[x for x in card["sources"] if x["id"]!=source["id"]]+[source]
  entries.append({"cardId":card_id,"imageId":stem,"fullSha256":hashlib.sha256(full.read_bytes()).hexdigest(),"thumbnailSha256":hashlib.sha256(thumb.read_bytes()).hexdigest(),"license":"Original AI-assisted illustrative reconstruction; no source image redistributed","sourceReference":SOURCE_URL,"sourcePage":page,"status":"Approved by owner"})
 data["contentVersion"]=data["catalogVersion"]=TARGET_VERSION
 PRODUCTION_CATALOG.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"); (ASSETS/"database/content-version.txt").write_text(f"{TARGET_VERSION}\n",encoding="utf-8")
 counts=build(PRODUCTION_CATALOG,PRODUCTION_DATABASE); (WORK/"reconstruction-batch-v221.json").write_text(json.dumps({"batch":"original-reconstruction-batch-v221","generatedAt":TODAY,"entries":entries,"build":counts},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 print(json.dumps({"updatedCards":len(entries),"build":counts},ensure_ascii=False,indent=2))
if __name__=="__main__": main()
