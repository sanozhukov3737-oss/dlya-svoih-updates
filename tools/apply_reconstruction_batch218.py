#!/usr/bin/env python3
"""Add the owner-approved batch of ten reconstructions (catalog 218)."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from PIL import Image
from build_catalog import PRODUCTION_CATALOG, PRODUCTION_DATABASE, ASSETS, build

ROOT = Path(__file__).resolve().parents[1]
TODAY = "2026-11-02"
TARGET_VERSION = 218
BANK = ROOT.parent / "aosearch/v218_candidates"
WORK = ROOT / "build/catalog218-reconstruction-batch"
SOURCE_URL = "https://sprotyvg7.com.ua/wp-content/uploads/2023/12/Katalog_Sredstva_inzhenernogo_vooruzhenia_Kniga_1.pdf"
ITEMS = [
    ("pdf198-4-5dee3b8868cc", "ЗРП-2", "zrp2_realistic.png", "reconstruction-v218-su-zrp2", 201),
    ("pdf198-4-ff16d13a4557", "КПТМ-3", "kptm3_realistic.png", "reconstruction-v218-su-kptm3", 275),
    ("pdf198-4-ebc54a331416", "КПОМ-2", "kpom2_realistic.png", "reconstruction-v218-su-kpom2", 295),
    ("pdf198-4-dfb4f4590f97", "КСФ-1С", "ksf1s_realistic.png", "reconstruction-v218-su-ksf1s", 297),
    ("pdf198-4-4e0a583772ab", "МЗМ-2", "mzm2_realistic.png", "reconstruction-v218-su-mzm2", 317),
    ("pdf198-4-d0047e546b19", "АДМ-8", "adm8_realistic.png", "reconstruction-v218-su-adm8", 327),
    ("pdf198-4-3a8456e147a5", "ЖДМ-6", "zhdm6_realistic.png", "reconstruction-v218-su-zhdm6", 331),
    ("pdf198-4-39c69f6edc3e", "ЗЗ-1", "zz1_realistic.png", "reconstruction-v218-su-zz1", 241),
    ("pdf198-4-2f7207415c43", "ВЗЗ-2", "vzz2_realistic.png", "reconstruction-v218-su-vzz2", 243),
    ("ref-v11-dshv", "ДШ-В", "dshv_realistic.png", "reconstruction-v218-su-dshv", 257),
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
    manifest = {"batch": "original-reconstruction-batch-v218", "generatedAt": TODAY, "entries": entries, "build": counts}
    (WORK / "reconstruction-batch-v218.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"updatedCards": len(entries), "addedImages": len(entries), "build": counts}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
