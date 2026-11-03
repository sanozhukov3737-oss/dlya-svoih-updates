#!/usr/bin/env python3
"""Add the owner-approved batch of ten reconstructions (catalog 217)."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from PIL import Image
from build_catalog import PRODUCTION_CATALOG, PRODUCTION_DATABASE, ASSETS, build

ROOT = Path(__file__).resolve().parents[1]
TODAY = "2026-11-02"
TARGET_VERSION = 217
BANK = ROOT.parent / "aosearch/v217_candidates"
WORK = ROOT / "build/catalog217-reconstruction-batch"
SOURCE_URL = "https://sprotyvg7.com.ua/wp-content/uploads/2023/12/Katalog_Sredstva_inzhenernogo_vooruzhenia_Kniga_1.pdf"
ITEMS = [
    ("pdf198-4-addc3e135482", "СЗ-3а", "sz3a_realistic.png", "reconstruction-v217-su-sz3a", 209),
    ("pdf198-4-a42ab908210e", "СЗ-1П", "sz1p_realistic.png", "reconstruction-v217-su-sz1p", 205),
    ("pdf198-4-155d002fe261", "СЗ-6М", "sz6m_realistic.png", "reconstruction-v217-su-sz6m", 215),
    ("pdf198-4-58ac3f8846f5", "КЗ-4", "kz4_realistic.png", "reconstruction-v217-su-kz4", 219),
    ("pdf198-4-bed78b0a2afe", "КЗ-5", "kz5_realistic.png", "reconstruction-v217-su-kz5", 221),
    ("pdf198-4-930b32821e93", "КЗ-7", "kz7_realistic.png", "reconstruction-v217-su-kz7", 225),
    ("pdf198-4-b5faaf3a0591", "КЗУ-2", "kzu2_realistic.png", "reconstruction-v217-su-kzu2", 229),
    ("pdf198-4-f80ea47067e3", "УМКЗ", "umkz_realistic.png", "reconstruction-v217-su-umkz", 231),
    ("pdf198-4-c7c41f456cf1", "КЗК", "kzk_realistic.png", "reconstruction-v217-su-kzk", 233),
    ("pdf198-4-164ad173cd9a", "ЛКЗ-80", "lkz80_realistic.png", "reconstruction-v217-su-lkz80", 235),
]


def main() -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    data = json.loads(PRODUCTION_CATALOG.read_text(encoding="utf-8"))
    if data["contentVersion"] not in (TARGET_VERSION - 1, TARGET_VERSION):
        raise RuntimeError(f"Unexpected catalog version {data['contentVersion']}")
    cards = {card["id"]: card for card in data["cards"]}
    entries = []
    for card_id, title, filename, stem, page in ITEMS:
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
            "caption": f"{title} — иллюстративная реконструкция внешнего вида по фотографии оригинального экземпляра в каталоге средств инженерного вооружения, PDF-страница {page}. Не фотография и не рабочий чертёж; маркировка и клейма не воспроизводятся.",
            "width": raster.width, "height": raster.height,
            "position": max((existing["position"] for existing in card["images"]), default=-1) + 1,
            "thumbnailPath": thumb_rel,
        }
        card["images"].append(image)
        card["images"].sort(key=lambda value: (value["position"], value["id"]))
        card["thumbnailPath"] = card["images"][0]["thumbnailPath"]
        source = {"id": f"source-{stem}", "title": f"{title} — фотография оригинального экземпляра на PDF-странице {page}; использована для проверки внешней формы, исходное изображение в каталог не копировалось", "url": SOURCE_URL, "accessedAt": TODAY}
        card["sources"] = [existing for existing in card["sources"] if existing["id"] != source["id"]]
        card["sources"].append(source)
        entries.append({"cardId": card_id, "imageId": stem, "fullSha256": hashlib.sha256(full.read_bytes()).hexdigest(), "thumbnailSha256": hashlib.sha256(thumb.read_bytes()).hexdigest(), "license": "Original AI-assisted illustrative reconstruction; no source image redistributed", "sourceReference": SOURCE_URL, "sourcePage": page, "status": "Approved by owner as part of the ten-image batch"})
    data["contentVersion"] = data["catalogVersion"] = TARGET_VERSION
    PRODUCTION_CATALOG.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (ASSETS / "database/content-version.txt").write_text(f"{TARGET_VERSION}\n", encoding="utf-8")
    counts = build(PRODUCTION_CATALOG, PRODUCTION_DATABASE)
    manifest = {"batch": "original-reconstruction-batch-v217", "generatedAt": TODAY, "entries": entries, "build": counts}
    (WORK / "reconstruction-batch-v217.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"updatedCards": len(entries), "addedImages": len(entries), "build": counts}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
