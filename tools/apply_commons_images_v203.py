#!/usr/bin/env python3
"""Add reviewed openly-licensed Wikimedia Commons images for catalog 203.

Batch v203: fuzes, AT mines, grenade rounds, US mine subsystems, initiation
boards, projectiles (112 cards searched). Only one candidate survived visual
review: the RPG-27 in the Tula State Museum of Weapons (CC BY-SA 4.0).
"""
from __future__ import annotations

import hashlib
import json
import time
import urllib.parse
from pathlib import Path
from urllib.request import Request, urlopen

from PIL import Image

from build_catalog import PRODUCTION_CATALOG, PRODUCTION_DATABASE, ASSETS, build

ROOT = Path(__file__).resolve().parents[1]
TODAY = "2026-11-01"
TARGET_VERSION = 203
WORK = ROOT / "build/catalog203-commons"
MANIFEST = WORK / "commons-images-v203.json"

ITEMS = [
    {
        "cardId": "pdf198-2-b94e25365d21",
        "file": "Tula State Museum of Weapons (79-58).jpg",
        "license": "CC BY-SA 4.0",
        "artist": "Vitaly V. Kuzmin",
        "page": "https://commons.wikimedia.org/wiki/File:Tula_State_Museum_of_Weapons_(79-58).jpg",
        "caption": "Реактивная противотанковая граната РПГ-27 (в центре витрины) среди одноразовых гранатомётов, экспозиция Тульского государственного музея оружия. Автор: Vitaly V. Kuzmin, Wikimedia Commons, CC BY-SA 4.0.",
    },
]


def download(file: str) -> Image.Image:
    """Fetch the file from Commons scaled so the long side is 1600 px."""
    quoted = urllib.parse.quote(file)
    url = f"https://commons.wikimedia.org/wiki/Special:FilePath/{quoted}?width=1600"
    request = Request(url, headers={"User-Agent": "DLYA-SVOIH-catalog-research/1.0"})
    with urlopen(request, timeout=120) as response:
        data = response.read()
    import io
    raster = Image.open(io.BytesIO(data))
    raster.load()
    if raster.mode in ("RGBA", "LA", "P"):
        background = Image.new("RGBA", raster.size, "white")
        raster = Image.alpha_composite(background, raster.convert("RGBA")).convert("RGB")
    else:
        raster = raster.convert("RGB")
    raster.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
    return raster


def save_asset(raster: Image.Image, stem: str) -> dict:
    full_rel = f"images/{stem}.webp"
    thumb_rel = f"thumbs/{stem}.webp"
    full = ASSETS / full_rel
    thumb = ASSETS / thumb_rel
    full.parent.mkdir(parents=True, exist_ok=True)
    thumb.parent.mkdir(parents=True, exist_ok=True)
    raster.save(full, "WEBP", quality=88, method=6)
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


def upsert_image(card: dict, item: dict, stem: str, asset: dict) -> None:
    image = {
        "id": stem,
        "localPath": asset["localPath"],
        "caption": item["caption"],
        "width": asset["width"],
        "height": asset["height"],
        "position": max((image["position"] for image in card["images"]), default=-1) + 1,
        "thumbnailPath": asset["thumbnailPath"],
    }
    card["images"] = [existing for existing in card["images"] if existing["id"] != image["id"]]
    card["images"].append(image)
    card["images"].sort(key=lambda value: (value["position"], value["id"]))
    card["thumbnailPath"] = card["images"][0]["thumbnailPath"]
    source = {
        "id": f"source-{stem}",
        "title": f"Wikimedia Commons — {item['file']} (автор: {item['artist']}, лицензия: {item['license']})",
        "url": item["page"],
        "accessedAt": TODAY,
    }
    card["sources"] = [existing for existing in card["sources"] if existing["id"] != source["id"]]
    card["sources"].append(source)


def main() -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    data = json.loads(PRODUCTION_CATALOG.read_text(encoding="utf-8"))
    if data["contentVersion"] not in (TARGET_VERSION - 1, TARGET_VERSION):
        raise RuntimeError(f"Expected catalog {TARGET_VERSION - 1} or idempotent {TARGET_VERSION}, got {data['contentVersion']}")
    cards = {card["id"]: card for card in data["cards"]}
    entries = []
    for index, item in enumerate(ITEMS):
        raster = download(item["file"])
        time.sleep(1.0)
        short = item["cardId"].replace("pdf198-", "p").replace("mine-audit-", "m")
        stem = f"photo-v203-{short}-{index}"
        asset = save_asset(raster, stem)
        card = cards[item["cardId"]]
        upsert_image(card, item, stem, asset)
        entries.append({**item, "stem": stem, **asset})
    data["contentVersion"] = TARGET_VERSION
    data["catalogVersion"] = TARGET_VERSION
    PRODUCTION_CATALOG.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (ASSETS / "database/content-version.txt").write_text(f"{TARGET_VERSION}\n", encoding="utf-8")
    counts = build(PRODUCTION_CATALOG, PRODUCTION_DATABASE)
    MANIFEST.write_text(json.dumps({
        "batch": "commons-open-license-v203",
        "generatedAt": TODAY,
        "policy": "Wikimedia Commons files with open licences (CC BY / CC BY-SA / public domain); visually verified against the card item; downscaled to 1600 px max, no retouching.",
        "entries": entries,
        "build": counts,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"updatedCards": sorted({item["cardId"] for item in ITEMS}),
                      "addedImages": len(ITEMS), "build": counts}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
