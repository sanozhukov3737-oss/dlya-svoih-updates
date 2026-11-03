#!/usr/bin/env python3
"""Add the exact-match CC BY Vapriikki photograph of an 81 mm smoke mortar round (catalog 209)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image

from build_catalog import PRODUCTION_CATALOG, PRODUCTION_DATABASE, ASSETS, build

ROOT = Path(__file__).resolve().parents[1]
TODAY = "2026-11-01"
TARGET_VERSION = 209
BANK = ROOT.parent / "aosearch" / "v210_candidates"
WORK = ROOT / "build/catalog209-ao"
MANIFEST = WORK / "archive-images-v210.json"
CARD_ID = "pdf198-7-c36a87511ad0"
STEM = "ao-v210-fi-81-smoke-mortar-round"
SOURCE_TITLE = "Vapriikin kuva-arkisto / Finna — 81 krh savuammus, CC BY 4.0"
SOURCE_URL = "https://api.finna.fi/v1/record?id=siiri.urn%3Anbn%3Afi-vapriikkihttp%253A%252F%252Fwww.profium.com%252Farchive%252FArchivedObject-3E3C1C4E-A07E-53FF-6040-B3526368FC48"


def main() -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    data = json.loads(PRODUCTION_CATALOG.read_text(encoding="utf-8"))
    if data["contentVersion"] not in (TARGET_VERSION - 1, TARGET_VERSION):
        raise RuntimeError(f"Expected catalog {TARGET_VERSION - 1} or {TARGET_VERSION}, got {data['contentVersion']}")
    card = next(card for card in data["cards"] if card["id"] == CARD_ID)
    raster = Image.open(BANK / "vapriikki_smoke_a.jpg").convert("RGB")
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
        "caption": "Финская 81-мм дымовая миномётная мина (81 krh savuammus). Фотография Vapriikin kuva-arkisto, CC BY 4.0.",
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
        "Добавлена архивная фотография Vapriikki с точным музейным обозначением «81 krh savuammus» — 81-мм дымовая миномётная мина. Лицензия изображения: CC BY 4.0."
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
        "license": "CC BY 4.0",
        "source": SOURCE_URL,
    }
    MANIFEST.write_text(json.dumps({
        "batch": "finnish-museum-ccby-v210",
        "generatedAt": TODAY,
        "policy": "Exact museum title 81 krh savuammus; Vapriikki archive; CC BY 4.0; visual review completed.",
        "entries": [entry],
        "build": counts,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"updatedCards": 1, "addedImages": 1, "build": counts}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
