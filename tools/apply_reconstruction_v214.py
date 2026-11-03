#!/usr/bin/env python3
"""Add the approved original Bd.Z.5127 reconstruction (catalog 213)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from PIL import Image
from build_catalog import PRODUCTION_CATALOG, PRODUCTION_DATABASE, ASSETS, build

ROOT = Path(__file__).resolve().parents[1]
TODAY = "2026-11-01"
TARGET_VERSION = 213
BANK = ROOT.parent / "aosearch"
WORK = ROOT / "build/catalog213-reconstruction"
MANIFEST = WORK / "reconstruction-v214.json"
CARD_ID = "pdf198-7-3b10014f84be"
STEM = "reconstruction-v214-de-bdz5127"
PHOTO_URL = "https://ersatzmilitaria.com/shop.php?code=53058"
HANDBOOK_URL = "https://michaelhiske.de/Allierte/UK/Handbook/Pamphlet12/12_011.htm"


def main() -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    data = json.loads(PRODUCTION_CATALOG.read_text(encoding="utf-8"))
    if data["contentVersion"] not in (TARGET_VERSION - 1, TARGET_VERSION):
        raise RuntimeError(f"Expected catalog {TARGET_VERSION - 1} or {TARGET_VERSION}, got {data['contentVersion']}")
    card = next(card for card in data["cards"] if card["id"] == CARD_ID)
    raster = Image.open(BANK / "bdz5127_realistic_v2.png").convert("RGB")
    raster.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
    full_rel = f"images/{STEM}.webp"
    thumb_rel = f"thumbs/{STEM}.webp"
    full, thumb = ASSETS / full_rel, ASSETS / thumb_rel
    full.parent.mkdir(parents=True, exist_ok=True)
    thumb.parent.mkdir(parents=True, exist_ok=True)
    raster.save(full, "WEBP", quality=90, method=6)
    miniature = raster.copy()
    miniature.thumbnail((256, 256), Image.Resampling.LANCZOS)
    miniature.save(thumb, "WEBP", quality=84, method=6)
    image = {
        "id": STEM,
        "localPath": full_rel,
        "caption": "Bd.Z.5127 — иллюстративная реконструкция внешнего вида по фотографиям разобранного экземпляра и описанию Handbook of Enemy Ammunition. Не фотография и не рабочий чертёж; мелкие грани и износ художественно обобщены.",
        "width": raster.width,
        "height": raster.height,
        "position": max((existing["position"] for existing in card["images"]), default=-1) + 1,
        "thumbnailPath": thumb_rel,
    }
    card["images"] = [existing for existing in card["images"] if existing["id"] != STEM]
    card["images"].append(image)
    card["images"].sort(key=lambda value: (value["position"], value["id"]))
    card["thumbnailPath"] = card["images"][0]["thumbnailPath"]
    card["body"] = card["body"].replace(
        "Отдельный подтверждённый наружный вид этого исполнения в карточку не добавлен.",
        "Добавлена самостоятельная иллюстративная реконструкция внешнего вида. Пропорции и профиль сверены с фотографиями разобранного экземпляра и описанием британского Handbook of Enemy Ammunition, Part 12. Это не фотография и не рабочий чертёж: мелкие грани и износ художественно обобщены."
    )
    sources = [
        {"id": f"source-{STEM}-photo", "title": "Bd.Z.5127 — фотографии разобранного инертного экземпляра; использованы только для проверки внешней формы, фотография в каталог не копировалась", "url": PHOTO_URL, "accessedAt": TODAY},
        {"id": f"source-{STEM}-handbook", "title": "Handbook of Enemy Ammunition, Part 12 — German Base Fuze Bd.Z.5127; описание корпуса, резьбы и трассёра", "url": HANDBOOK_URL, "accessedAt": TODAY},
    ]
    for source in sources:
        card["sources"] = [existing for existing in card["sources"] if existing["id"] != source["id"]]
        card["sources"].append(source)
    data["contentVersion"] = TARGET_VERSION
    data["catalogVersion"] = TARGET_VERSION
    PRODUCTION_CATALOG.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (ASSETS / "database/content-version.txt").write_text(f"{TARGET_VERSION}\n", encoding="utf-8")
    counts = build(PRODUCTION_CATALOG, PRODUCTION_DATABASE)
    entry = {
        "cardId": CARD_ID, "imageId": STEM, "localPath": full_rel, "thumbnailPath": thumb_rel,
        "fullSha256": hashlib.sha256(full.read_bytes()).hexdigest(),
        "thumbnailSha256": hashlib.sha256(thumb.read_bytes()).hexdigest(),
        "license": "Original AI-assisted illustrative reconstruction; no source photograph redistributed",
        "sourceReferences": [PHOTO_URL, HANDBOOK_URL],
        "status": "Approved by owner before inclusion; illustrative, not a verified technical drawing"
    }
    MANIFEST.write_text(json.dumps({"batch": "original-reconstruction-v214", "generatedAt": TODAY, "entries": [entry], "build": counts}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"updatedCards": 1, "addedImages": 1, "build": counts}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
