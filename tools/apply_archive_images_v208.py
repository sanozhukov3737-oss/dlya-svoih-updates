#!/usr/bin/env python3
"""Add ten visually matched public-domain manual illustrations (catalog 207).

Sources: US War Department manuals TM 9-1985-3 (1953), TM-E 30-451
(1945), and TM 9-1904 (1944), marked public domain on archive.org.
Only exact model/variant matches were accepted. The M51 drawing is explicitly
used for M51B1 because the manual states that B1/B2 are manufacturing
alternatives with identical functioning and shows the common M51 drawing.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image

from build_catalog import PRODUCTION_CATALOG, PRODUCTION_DATABASE, ASSETS, build

ROOT = Path(__file__).resolve().parents[1]
TODAY = "2026-11-01"
TARGET_VERSION = 207
BANK = ROOT.parent / "aosearch" / "v208_crops"
WORK = ROOT / "build/catalog207-ao"
MANIFEST = WORK / "archive-images-v208.json"

TM3 = "https://archive.org/details/TM9-1985-3"
TME = "https://archive.org/details/TME-30-4511945"
TM4 = "https://archive.org/details/TM9-1904"

ITEMS = [
    {"cardId": "pdf198-7-8f59c8c41e9f", "stem": "de-pzgr18", "source": "tm3", "figure": "рис. 354", "caption": "Немецкий 37-мм бронебойный снаряд 3,7 cm Pzgr.Patr.18 в разрезе. Рис. 354 из TM 9-1985-3 (1953), общественное достояние."},
    {"cardId": "pdf198-7-50b19625ebc7", "stem": "de-sprgr40", "source": "tm3", "figure": "рис. 356", "caption": "Немецкий 37-мм осколочно-фугасный снаряд 3,7 cm Sprgr.Patr.40 в разрезе. Рис. 356 из TM 9-1985-3 (1953), общественное достояние."},
    {"cardId": "pdf198-7-85cae47ebd10", "stem": "de-az5045", "source": "tm3", "figure": "рис. 559", "caption": "Немецкий головной ударный взрыватель A.Z.5045 в разрезе. Рис. 559 из TM 9-1985-3 (1953), общественное достояние."},
    {"cardId": "pdf198-7-8568b4bd9315", "stem": "de-az39", "source": "tm3", "figure": "рис. 575", "caption": "Немецкий головной взрыватель A.Z.39: разрезы до и после взведения. Рис. 575 из TM 9-1985-3 (1953), общественное достояние."},
    {"cardId": "pdf198-7-a4fbee9d5eea", "stem": "de-wgrz38", "source": "tm3", "figure": "рис. 591", "caption": "Немецкий миномётный взрыватель Wgr.Z.38 в разрезе. Рис. 591 из TM 9-1985-3 (1953), общественное достояние."},
    {"cardId": "pdf198-7-cbb28e1e9450", "stem": "de-wgr36", "source": "tm3", "figure": "рис. 542", "caption": "Немецкая 50-мм осколочная миномётная мина 5 cm Wgr.36 в разрезе, вид хвостовика сверху. Рис. 542 из TM 9-1985-3 (1953), общественное достояние."},
    {"cardId": "pdf198-7-8655eec0ab78", "stem": "de-wurf326", "source": "tme", "figure": "рис. 128", "caption": "Немецкая осколочная граната Wurfgranatpatrone 326 LP для сигнального пистолета. Рис. 128 из TM-E 30-451 (1945), общественное достояние."},
    {"cardId": "pdf198-7-29e3e187a9e7", "stem": "us-apc-m51", "source": "tm4", "figure": "рис. 136", "caption": "Американский 37-мм бронебойно-каморный выстрел APC M51; пособие указывает M51B1 как производственный вариант M51. Рис. 136 из TM 9-1904 (1944), общественное достояние."},
    {"cardId": "pdf198-7-e4ff0c870e1a", "stem": "us-m46", "source": "tm4", "figure": "рис. 150", "caption": "Американский мгновенный донный взрыватель P.D. M46 с белой головной частью, внешний вид и разрез. Рис. 150 из TM 9-1904 (1944), общественное достояние."},
    {"cardId": "pdf198-7-6b33c9ec9529", "stem": "us-m47", "source": "tm4", "figure": "рис. 150", "caption": "Американский донный взрыватель P.D. M47 с замедлением и чёрной головной частью, внешний вид и разрез. Рис. 150 из TM 9-1904 (1944), общественное достояние."},
]

SOURCES = {
    "tm3": ("TM 9-1985-3 German Explosive Ordnance (Projectiles and Projectile Fuzes), 1953 — US War Department, общественное достояние", TM3),
    "tme": ("TM-E 30-451 Handbook on German Military Forces, 1945 — US War Department, общественное достояние", TME),
    "tm4": ("TM 9-1904 Ammunition Inspection Guide, 1944 — US War Department, общественное достояние", TM4),
}


def save_asset(raster: Image.Image, stem: str) -> dict:
    raster.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
    full_rel = f"images/ao-v208-{stem}.webp"
    thumb_rel = f"thumbs/ao-v208-{stem}.webp"
    full = ASSETS / full_rel
    thumb = ASSETS / thumb_rel
    full.parent.mkdir(parents=True, exist_ok=True)
    thumb.parent.mkdir(parents=True, exist_ok=True)
    raster.save(full, "WEBP", quality=90, method=6)
    miniature = raster.copy()
    miniature.thumbnail((256, 256), Image.Resampling.LANCZOS)
    miniature.save(thumb, "WEBP", quality=84, method=6)
    return {
        "localPath": full_rel,
        "thumbnailPath": thumb_rel,
        "width": raster.width,
        "height": raster.height,
        "fullSha256": hashlib.sha256(full.read_bytes()).hexdigest(),
        "thumbnailSha256": hashlib.sha256(thumb.read_bytes()).hexdigest(),
    }


def main() -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    data = json.loads(PRODUCTION_CATALOG.read_text(encoding="utf-8"))
    if data["contentVersion"] not in (TARGET_VERSION - 1, TARGET_VERSION):
        raise RuntimeError(f"Expected catalog {TARGET_VERSION - 1} or {TARGET_VERSION}, got {data['contentVersion']}")
    cards = {card["id"]: card for card in data["cards"]}
    entries = []
    for item in ITEMS:
        card = cards[item["cardId"]]
        stem = f"ao-v208-{item['stem']}"
        raster = Image.open(BANK / f"{item['stem']}.png").convert("RGB")
        asset = save_asset(raster, stem)
        image = {
            "id": stem,
            "localPath": asset["localPath"],
            "caption": item["caption"],
            "width": asset["width"],
            "height": asset["height"],
            "position": max((existing["position"] for existing in card["images"]), default=-1) + 1,
            "thumbnailPath": asset["thumbnailPath"],
        }
        card["images"] = [existing for existing in card["images"] if existing["id"] != stem]
        card["images"].append(image)
        card["images"].sort(key=lambda value: (value["position"], value["id"]))
        card["thumbnailPath"] = card["images"][0]["thumbnailPath"]
        title, url = SOURCES[item["source"]]
        source = {"id": f"source-{stem}", "title": title, "url": url, "accessedAt": TODAY}
        card["sources"] = [existing for existing in card["sources"] if existing["id"] != source["id"]]
        card["sources"].append(source)
        entries.append({**item, "imageId": stem, **asset})
    data["contentVersion"] = TARGET_VERSION
    data["catalogVersion"] = TARGET_VERSION
    PRODUCTION_CATALOG.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (ASSETS / "database/content-version.txt").write_text(f"{TARGET_VERSION}\n", encoding="utf-8")
    counts = build(PRODUCTION_CATALOG, PRODUCTION_DATABASE)
    MANIFEST.write_text(json.dumps({
        "batch": "archive-public-domain-v208",
        "generatedAt": TODAY,
        "policy": "Exact model/variant matches only; visually reviewed crops from US Government public-domain manuals; no retouching except cropping and downscaling.",
        "entries": entries,
        "build": counts,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"updatedCards": len(ITEMS), "addedImages": len(entries), "build": counts}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
