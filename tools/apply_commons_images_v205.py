#!/usr/bin/env python3
"""Add reviewed openly-licensed Wikimedia Commons images for catalog 204.

Batch v205: gun/tank and mortar ammunition (175 cards searched). Direct index
queries returned almost nothing usable; targeted museum queries surfaced five
presentable Finnish museum photos (public domain, author MKFI) of typical
Soviet-family shells. Exact modification cannot be verified from the photos,
so captions say exactly that.
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
TARGET_VERSION = 204
WORK = ROOT / "build/catalog204-commons"
MANIFEST = WORK / "commons-images-v205.json"

ITEMS = [
    {
        "cardId": "pdf198-5-ed1c3de7d02c",
        "file": "130 mm M-46 trotyl shell Hämeenlinna.JPG",
        "license": "Public domain",
        "artist": "MKFI",
        "page": "https://commons.wikimedia.org/wiki/File:130_mm_M-46_trotyl_shell_H%C3%A4meenlinna.JPG",
        "caption": "Типовой 130-мм осколочно-фугасный тротиловый снаряд к пушке М-46; точная модификация по снимку не определяется. Финский музей Артиллерии (Хямеэнлинна). Автор: MKFI, Wikimedia Commons, общественное достояние.",
    },
    {
        "cardId": "pdf198-5-f1dc79f98bee",
        "file": "130 mm M-46 trotyl shell Hämeenlinna.JPG",
        "license": "Public domain",
        "artist": "MKFI",
        "page": "https://commons.wikimedia.org/wiki/File:130_mm_M-46_trotyl_shell_H%C3%A4meenlinna.JPG",
        "caption": "Типовой 130-мм осколочно-фугасный тротиловый снаряд к пушке М-46; точная модификация по снимку не определяется. Финский музей Артиллерии (Хямеэнлинна). Автор: MKFI, Wikimedia Commons, общественное достояние.",
    },
    {
        "cardId": "pdf198-5-a923224f6a05",
        "file": "122 H 38 shell.JPG",
        "license": "Public domain",
        "artist": "MKFI",
        "page": "https://commons.wikimedia.org/wiki/File:122_H_38_shell.JPG",
        "caption": "122-мм осколочно-фугасный снаряд к гаубице образца 1938 года (финская маркировка 122 H 38, семейство ОФ-462/ВОФ-463); точная модификация по снимку не определяется. Финский музей Артиллерии (Хямеэнлинна). Автор: MKFI, Wikimedia Commons, общественное достояние.",
    },
    {
        "cardId": "pdf198-5-509244a92fd7",
        "file": "122 H 38 shell.JPG",
        "license": "Public domain",
        "artist": "MKFI",
        "page": "https://commons.wikimedia.org/wiki/File:122_H_38_shell.JPG",
        "caption": "122-мм осколочно-фугасный снаряд к гаубице образца 1938 года (финская маркировка 122 H 38, семейство ОФ-462/ВОФ-463); точная модификация по снимку не определяется. Финский музей Артиллерии (Хямеэнлинна). Автор: MKFI, Wikimedia Commons, общественное достояние.",
    },
    {
        "cardId": "pdf198-5-628fffd31244",
        "file": "152 K 77 shell.JPG",
        "license": "Public domain",
        "artist": "MKFI",
        "page": "https://commons.wikimedia.org/wiki/File:152_K_77_shell.JPG",
        "caption": "Типовой 152-мм осколочно-фугасный снаряд (финская маркировка 152 K 77); точная модификация по снимку не определяется. Финский музей Артиллерии (Хямеэнлинна). Автор: MKFI, Wikimedia Commons, общественное достояние.",
    },
    {
        "cardId": "pdf198-5-9b4ee1dd7ec3",
        "file": "152 mm howitzer shell Hämeenlinna 1.JPG",
        "license": "Public domain",
        "artist": "MKFI",
        "page": "https://commons.wikimedia.org/wiki/File:152_mm_howitzer_shell_H%C3%A4meenlinna_1.JPG",
        "caption": "152-мм гаубичный снаряд в финской музейной экспозиции (Хямеэнлинна); точная модификация по снимку не определяется. Автор: MKFI, Wikimedia Commons, общественное достояние.",
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
        stem = f"photo-v205-{short}-{index}"
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
        "batch": "commons-open-license-v205",
        "generatedAt": TODAY,
        "policy": "Wikimedia Commons files with open licences (CC BY / CC BY-SA / public domain); visually verified against the card item; downscaled to 1600 px max, no retouching.",
        "entries": entries,
        "build": counts,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"updatedCards": sorted({item["cardId"] for item in ITEMS}),
                      "addedImages": len(ITEMS), "build": counts}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
