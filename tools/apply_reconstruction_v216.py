#!/usr/bin/env python3
"""Add the approved original E.Kzdr.C/28 reconstruction (catalog 215)."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from PIL import Image
from build_catalog import PRODUCTION_CATALOG, PRODUCTION_DATABASE, ASSETS, build

ROOT = Path(__file__).resolve().parents[1]
TODAY = "2026-11-01"
TARGET_VERSION = 215
BANK = ROOT.parent / "aosearch"
WORK = ROOT / "build/catalog215-reconstruction"
CARD_ID = "pdf198-7-add659efdb98"
STEM = "reconstruction-v216-de-ekzdrc28"
SOURCE_URL = "https://www.nachschublager.de/p/kriegsmarine-kopfzuender-e-kzdr-c-28-bgt"


def main() -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    data = json.loads(PRODUCTION_CATALOG.read_text(encoding="utf-8"))
    if data["contentVersion"] not in (TARGET_VERSION - 1, TARGET_VERSION):
        raise RuntimeError(f"Unexpected catalog version {data['contentVersion']}")
    card = next(card for card in data["cards"] if card["id"] == CARD_ID)
    raster = Image.open(BANK / "ekzdr_realistic.png").convert("RGB")
    raster.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
    full_rel, thumb_rel = f"images/{STEM}.webp", f"thumbs/{STEM}.webp"
    full, thumb = ASSETS / full_rel, ASSETS / thumb_rel
    full.parent.mkdir(parents=True, exist_ok=True)
    thumb.parent.mkdir(parents=True, exist_ok=True)
    raster.save(full, "WEBP", quality=90, method=6)
    miniature = raster.copy()
    miniature.thumbnail((256, 256), Image.Resampling.LANCZOS)
    miniature.save(thumb, "WEBP", quality=84, method=6)
    image = {
        "id": STEM, "localPath": full_rel,
        "caption": "E.Kzdr.C/28 — иллюстративная реконструкция внешнего вида по фотографиям оригинального экземпляра. Не фотография и не рабочий чертёж; маркировка производителя и клейма не воспроизводятся.",
        "width": raster.width, "height": raster.height,
        "position": max((existing["position"] for existing in card["images"]), default=-1) + 1,
        "thumbnailPath": thumb_rel,
    }
    card["images"] = [existing for existing in card["images"] if existing["id"] != STEM]
    card["images"].append(image)
    card["images"].sort(key=lambda value: (value["position"], value["id"]))
    card["thumbnailPath"] = card["images"][0]["thumbnailPath"]
    card["body"] = card["body"].replace(
        "Отдельный подтверждённый наружный вид этого исполнения в карточку не добавлен.",
        "Добавлена самостоятельная иллюстративная реконструкция внешнего вида E.Kzdr.C/28 по фотографиям оригинального экземпляра с маркировкой C/28. Это не фотография и не рабочий чертёж; маркировка производителя и клейма не воспроизводятся."
    )
    source = {"id": f"source-{STEM}", "title": "E.Kzdr.C/28 — фотографии оригинального экземпляра с маркировкой C/28; использованы для проверки внешней формы, исходная фотография в каталог не копировалась", "url": SOURCE_URL, "accessedAt": TODAY}
    card["sources"] = [existing for existing in card["sources"] if existing["id"] != source["id"]]
    card["sources"].append(source)
    data["contentVersion"] = data["catalogVersion"] = TARGET_VERSION
    PRODUCTION_CATALOG.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (ASSETS / "database/content-version.txt").write_text(f"{TARGET_VERSION}\n", encoding="utf-8")
    counts = build(PRODUCTION_CATALOG, PRODUCTION_DATABASE)
    manifest = {"batch": "original-reconstruction-v216", "generatedAt": TODAY, "entries": [{"cardId": CARD_ID, "imageId": STEM, "fullSha256": hashlib.sha256(full.read_bytes()).hexdigest(), "thumbnailSha256": hashlib.sha256(thumb.read_bytes()).hexdigest(), "license": "Original AI-assisted illustrative reconstruction; no source photograph redistributed", "sourceReference": SOURCE_URL, "status": "Approved by owner before inclusion"}], "build": counts}
    (WORK / "reconstruction-v216.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"updatedCards": 1, "addedImages": 1, "build": counts}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
