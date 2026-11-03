#!/usr/bin/env python3
"""Add the public-domain An.Z.29 illustration from TM 9-1985-2 (catalog 212)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image

from build_catalog import PRODUCTION_CATALOG, PRODUCTION_DATABASE, ASSETS, build

ROOT = Path(__file__).resolve().parents[1]
TODAY = "2026-11-01"
TARGET_VERSION = 212
BANK = ROOT.parent / "aosearch" / "v212_candidates"
WORK = ROOT / "build/catalog212-ao"
MANIFEST = WORK / "archive-images-v213.json"
CARD_ID = "pdf198-7-a2e70d9c5a2c"
STEM = "ao-v213-de-anz29-figure253"
SOURCE_TITLE = "TM 9-1985-2/TO 11A-1-26, German Explosive Ordnance (1953), figure 253 — ANZ-29 Friction Igniter Pull Type, PDF p. 292; US Government work"
SOURCE_URL = "https://www.gyges.dk/TM9-1985-2-German.pdf"


def main() -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    data = json.loads(PRODUCTION_CATALOG.read_text(encoding="utf-8"))
    if data["contentVersion"] not in (TARGET_VERSION - 1, TARGET_VERSION):
        raise RuntimeError(f"Expected catalog {TARGET_VERSION - 1} or {TARGET_VERSION}, got {data['contentVersion']}")
    card = next(card for card in data["cards"] if card["id"] == CARD_ID)
    raster = Image.open(BANK / "anz29_figure253.jpg").convert("RGB")
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
        "caption": "An.Z.29 — фрикционный воспламенитель натяжного действия в разрезе. Рисунок 253 из TM 9-1985-2 (1953), PDF-страница 292; официальное издание правительства США.",
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
        "Добавлен рисунок 253 «ANZ-29 Friction Igniter Pull Type» из официального пособия США TM 9-1985-2 (1953), PDF-страница 292. Схема показывает воспламенитель в разрезе с подписями деталей."
    )
    source = {"id": f"source-{STEM}", "title": SOURCE_TITLE, "url": SOURCE_URL, "accessedAt": TODAY}
    card["sources"] = [existing for existing in card["sources"] if existing["id"] != source["id"]]
    card["sources"].append(source)
    data["contentVersion"] = TARGET_VERSION
    data["catalogVersion"] = TARGET_VERSION
    PRODUCTION_CATALOG.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (ASSETS / "database/content-version.txt").write_text(f"{TARGET_VERSION}\n", encoding="utf-8")
    counts = build(PRODUCTION_CATALOG, PRODUCTION_DATABASE)
    entry = {
        "cardId": CARD_ID,
        "imageId": STEM,
        "localPath": full_rel,
        "thumbnailPath": thumb_rel,
        "fullSha256": hashlib.sha256(full.read_bytes()).hexdigest(),
        "thumbnailSha256": hashlib.sha256(thumb.read_bytes()).hexdigest(),
        "license": "US Government work / public domain",
        "source": SOURCE_URL,
    }
    MANIFEST.write_text(json.dumps({
        "batch": "us-government-manual-v213",
        "generatedAt": TODAY,
        "policy": "Exact An.Z.29 figure and associated description; visual review completed.",
        "entries": [entry],
        "build": counts,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"updatedCards": 1, "addedImages": 1, "build": counts}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
