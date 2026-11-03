#!/usr/bin/env python3
"""Add the owner-approved batch of ten reconstructions (catalog 216)."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from PIL import Image
from build_catalog import PRODUCTION_CATALOG, PRODUCTION_DATABASE, ASSETS, build

ROOT = Path(__file__).resolve().parents[1]
TODAY = "2026-11-02"
TARGET_VERSION = 216
BANK = ROOT.parent / "aosearch"
WORK = ROOT / "build/catalog216-reconstruction-batch"
ITEMS = [
    ("pdf198-7-4a5b8c470b68", "L.W.M.Z.23", "lwmz23_realistic.png", "reconstruction-v216-de-lwmz23", "https://ersatzmilitaria.com/shop.php?code=51873", "фотографии оригинального экземпляра"),
    ("pdf198-7-faab4176cade", "T.Mi.Z.44", "tmiz44_realistic.png", "reconstruction-v216-de-tmiz44", "https://www.bulletpicker.com/pdf/TM-5-223C.pdf", "рисунка 38 пособия TM 5-223C"),
    ("mine-audit-v25-us-m2a4", "M2A4", "m2a4_realistic.png", "reconstruction-v216-us-m2a4", "https://bulletpicker.com/landmine_-apers_-m2a4.html", "справочного рисунка, внешне общего для M2A3/M2A4"),
    ("mine-audit-v25-su-tm-73", "ТМ-73", "tm73_realistic.png", "reconstruction-v216-su-tm73", "https://sappers.org/en/handbook/mines/anti-tank-side-attack/tm-73", "фотографии общего вида оригинального экземпляра"),
    ("mine-audit-v25-us-m3", "M3", "m3_realistic.png", "reconstruction-v216-us-m3", "https://uxoinfo.com/uxofiles/gallery/Landmines/Landmines.html", "фотографии оригинального экземпляра в справочной галерее UXOInfo"),
    ("ref-v8-pk-p2mk2-at", "P2 Mk2 AT", "p2mk2at_realistic.png", "reconstruction-v216-pk-p2mk2at", "https://www.apminebanconvention.org/fileadmin/_APMBC-DOCUMENTS/Art7Reports/Afghanistan-Article_7_report-April2013.pdf", "фотографии оригинального экземпляра в приложении H отчёта"),
    ("mine-audit-v25-su-pmd-7", "ПМД-7", "pmd7_realistic.png", "reconstruction-v216-su-pmd7", "https://bulletpicker.com/landmine_-apers_-pmd-7.html", "справочного рисунка ПМД-7"),
    ("mine-audit-v25-su-pmd-7ts", "ПМД-7Ц", "pmd7ts_realistic.png", "reconstruction-v216-su-pmd7ts", "https://bulletpicker.com/pdf/TM-5-280-1971.pdf", "рисунка 6-108 пособия TM 5-280"),
    ("mine-audit-v25-fr-model-1953", "Model 1953", "model1953_realistic.png", "reconstruction-v216-fr-model1953", "https://bulletpicker.com/pdf/TM-5-280-1971.pdf", "рисунка 9-85 пособия TM 5-280"),
    ("mine-audit-v25-fr-model-1954", "Model 1954", "model1954_realistic.png", "reconstruction-v216-fr-model1954", "https://bulletpicker.com/pdf/TM-5-280-1971.pdf", "рисунка 9-85 пособия TM 5-280"),
]


def main() -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    data = json.loads(PRODUCTION_CATALOG.read_text(encoding="utf-8"))
    if data["contentVersion"] not in (TARGET_VERSION - 1, TARGET_VERSION):
        raise RuntimeError(f"Unexpected catalog version {data['contentVersion']}")
    cards = {card["id"]: card for card in data["cards"]}
    entries = []
    for card_id, title, filename, stem, source_url, source_form in ITEMS:
        card = cards[card_id]
        card["images"] = [existing for existing in card["images"] if existing["id"] != stem]
        raster = Image.open(BANK / filename).convert("RGB")
        raster.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
        full_rel, thumb_rel = f"images/{stem}.webp", f"thumbs/{stem}.webp"
        full, thumb = ASSETS / full_rel, ASSETS / thumb_rel
        full.parent.mkdir(parents=True, exist_ok=True)
        thumb.parent.mkdir(parents=True, exist_ok=True)
        raster.save(full, "WEBP", quality=90, method=6)
        miniature = raster.copy()
        miniature.thumbnail((256, 256), Image.Resampling.LANCZOS)
        miniature.save(thumb, "WEBP", quality=84, method=6)
        image = {
            "id": stem, "localPath": full_rel,
            "caption": f"{title} — иллюстративная реконструкция внешнего вида по {source_form}. Не фотография и не рабочий чертёж; маркировка и клейма не воспроизводятся.",
            "width": raster.width, "height": raster.height,
            "position": max((existing["position"] for existing in card["images"]), default=-1) + 1,
            "thumbnailPath": thumb_rel,
        }
        card["images"] = [existing for existing in card["images"] if existing["id"] != stem]
        card["images"].append(image)
        card["images"].sort(key=lambda value: (value["position"], value["id"]))
        card["thumbnailPath"] = card["images"][0]["thumbnailPath"]
        source = {"id": f"source-{stem}", "title": f"{title} — {source_form}; использованы для проверки внешней формы, исходное изображение в каталог не копировалось", "url": source_url, "accessedAt": TODAY}
        card["sources"] = [existing for existing in card["sources"] if existing["id"] != source["id"]]
        card["sources"].append(source)
        entries.append({"cardId": card_id, "imageId": stem, "fullSha256": hashlib.sha256(full.read_bytes()).hexdigest(), "thumbnailSha256": hashlib.sha256(thumb.read_bytes()).hexdigest(), "license": "Original AI-assisted illustrative reconstruction; no source image redistributed", "sourceReference": source_url, "status": "Approved by owner as part of the ten-image batch"})
    data["contentVersion"] = data["catalogVersion"] = TARGET_VERSION
    PRODUCTION_CATALOG.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (ASSETS / "database/content-version.txt").write_text(f"{TARGET_VERSION}\n", encoding="utf-8")
    counts = build(PRODUCTION_CATALOG, PRODUCTION_DATABASE)
    manifest = {"batch": "original-reconstruction-batch-v216", "generatedAt": TODAY, "entries": entries, "build": counts}
    (WORK / "reconstruction-batch-v216.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"updatedCards": len(entries), "addedImages": len(entries), "build": counts}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
