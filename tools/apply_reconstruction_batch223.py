#!/usr/bin/env python3
"""Add the 23 owner-approved illustrative reconstructions (catalog 223)."""
from __future__ import annotations
import hashlib,json
from pathlib import Path
from PIL import Image
from build_catalog import PRODUCTION_CATALOG,PRODUCTION_DATABASE,ASSETS,build
ROOT=Path(__file__).resolve().parents[1]; TODAY="2026-11-02"; VERSION=223
BANK=ROOT.parent/"aosearch/v223_reconstructions"; WORK=ROOT/"build/catalog223-reconstruction-batch"
ITEMS=[
("mine-audit-v25-us-m2a4b2","M2A4B2","01_m2a4b2","https://www.bulletpicker.com/landmine_-apers_-m2a4.html"),
("mine-audit-v25-us-m66","M66","02_m66","https://www.uxoinfo.com/"),
("mine-audit-v25-de-riegelmine-44","Riegelmine 44","03_riegelmine44","https://www.lexpev.nl/mines-and-charges/europe/germany/riegelmine-44.html"),
("ref-v9-kd8","КД 8-А","04_kd8a","https://ru.djvu.online/file/gfvkfSoH5rj8W"),
("ordnance-v27-avu","АВУ","05_avu","https://www.gichd.org/fileadmin/user_upload/Explosive_Ordnance_Guide_for_Ukraine__GICHD___Third_Edition.pdf"),
("pdf198-7-1fc9387e7f88","РГУ-38 Дьяконова","07_rgu38","https://www.lexpev.nl/grenades/soviet-russia/rgu-38.html"),
("pdf198-7-08662ce72bae","Dosenmine 44","08_dosenmine44","https://www.lexpev.nl/mines-and-charges/europe/germany/dosenmine-44.html"),
("mine-audit-v26-su-pkm-25","ПКМ-25","10_pkm25","https://allmines.net/catalog/russia/mines/pkm25/"),
("mine-audit-v26-su-pkm-100","ПКМ-100","11_pkm100","https://allmines.net/catalog/russia/mines/pkm25/"),
("mine-audit-v26-su-amd-4-500","АМД-4-500","12_amd4_500","https://allmines.net/catalog/russia/mines/amd4/"),
("mine-audit-v26-su-amd-4-1000","АМД-4-1000","13_amd4_1000","https://allmines.net/catalog/russia/mines/amd4/"),
("mine-audit-v26-su-gm","ГМ","14_gm","https://allmines.net/catalog/russia/mines/gm/"),
("mine-audit-v26-su-ugm","УГМ","15_ugm","https://allmines.net/catalog/russia/mines/gm/"),
("mine-audit-v26-su-prm","ПРМ","16_prm","https://allmines.net/catalog/russia/mines/prm/"),
("mine-audit-v26-su-tum-500","ТУМ-500","18_tum500","https://allmines.net/catalog/russia/mines/tum/"),
("mine-audit-v26-su-krm","КРМ","19_krm","https://allmines.net/catalog/russia/mines/krm/"),
("ref-v8-ar-md","AR-MD","20_armd","https://arcus.bg/fuze-ar-md-for-82-mm-and-120-mm-mortar-ammunition/"),
("mine-audit-v25-us-mk-57","Mk 57","21_mk57","https://www.navweaps.com/Weapons/WAMUS_Mines.php"),
("ref-v9-il-no3","No. 3 AP","22_no3ap","https://commons.wikimedia.org/wiki/File:No._3_ap_mine.png"),
("ordnance-v27-pmm-1-kuba","PMM-1","23_pmm1","https://metis.fenixinsight.com/munition/mine/pmm-1"),
("mine-audit-v26-us-hammerhead-encapsulated-effector","Hammerhead Encapsulated Effector","24_hammerhead","https://www.strikepod.com/xluuv-offensive-mining/"),
("eng-pp-mi-ba","PP-Mi-Ba","25_ppmiba","https://bulletpicker.com/landmine_-apers_-pp-mi-ba.html"),
("mine-audit-v25-ru-mdm-3-mod-1","МДМ-3 мод. 1","26_mdm3","https://web.archive.org/web/20090419060403id_/http://www.rusarm.ru/cataloque/navy/navy.pdf")]
def main():
 WORK.mkdir(parents=True,exist_ok=True); data=json.loads(PRODUCTION_CATALOG.read_text(encoding="utf-8")); cards={c["id"]:c for c in data["cards"]}; entries=[]
 for card_id,title,slug,url in ITEMS:
  stem=f"reconstruction-v223-{slug.replace('_','-')}"; card=cards[card_id]
  if any(not x["id"].startswith("reconstruction-v223-") for x in card["images"]): raise RuntimeError(f"Unexpected existing image: {card_id}")
  raster=Image.open(BANK/f"{slug}.png").convert("RGB"); raster.thumbnail((1600,1600),Image.Resampling.LANCZOS)
  full_rel,thumb_rel=f"images/{stem}.webp",f"thumbs/{stem}.webp"; full,thumb=ASSETS/full_rel,ASSETS/thumb_rel
  raster.save(full,"WEBP",quality=90,method=6); miniature=raster.copy(); miniature.thumbnail((256,256),Image.Resampling.LANCZOS); miniature.save(thumb,"WEBP",quality=84,method=6)
  card["images"]=[{"id":stem,"localPath":full_rel,"caption":f"{title} — иллюстративная реконструкция внешнего вида по открытому изображению оригинального экземпляра или музейной схеме. Не фотография и не рабочий чертёж; маркировка и клейма не воспроизводятся.","width":raster.width,"height":raster.height,"position":0,"thumbnailPath":thumb_rel}]; card["thumbnailPath"]=thumb_rel
  source={"id":f"source-{stem}","title":f"{title} — открытый источник внешнего вида; исходное изображение в каталог не копировалось","url":url,"accessedAt":TODAY}; card["sources"]=[x for x in card["sources"] if not x["id"].startswith("source-reconstruction-v223-")]+[source]
  entries.append({"cardId":card_id,"imageId":stem,"fullSha256":hashlib.sha256(full.read_bytes()).hexdigest(),"thumbnailSha256":hashlib.sha256(thumb.read_bytes()).hexdigest(),"license":"Original AI-assisted illustrative reconstruction; no source image redistributed","sourceReference":url,"status":"Approved by owner"})
 data["contentVersion"]=data["catalogVersion"]=VERSION; PRODUCTION_CATALOG.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"); (ASSETS/"database/content-version.txt").write_text(f"{VERSION}\n",encoding="utf-8")
 counts=build(PRODUCTION_CATALOG,PRODUCTION_DATABASE); (WORK/"reconstruction-batch-v223.json").write_text(json.dumps({"batch":"original-reconstruction-batch-v223","generatedAt":TODAY,"entries":entries,"build":counts},ensure_ascii=False,indent=2)+"\n",encoding="utf-8"); print(json.dumps({"added":len(entries),"build":counts},ensure_ascii=False,indent=2))
if __name__=="__main__": main()
