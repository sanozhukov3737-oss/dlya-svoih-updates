#!/usr/bin/env python3
"""Add reviewed Yugoimport factory visuals for catalog 200.

The PDFs are official one-page product sheets. The selected embedded raster is
preserved without upscaling or retouching; authorship and an open licence are
not stated by the source and are recorded as unknown.
"""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
from urllib.request import Request, urlopen

from PIL import Image
from pypdf import PdfReader

from build_catalog import PRODUCTION_CATALOG, PRODUCTION_DATABASE, ASSETS, build

ROOT = Path(__file__).resolve().parents[1]
TODAY = "2026-10-31"
TARGET_VERSION = 200
WORK = ROOT / "build/catalog200-yugo"
SOURCES_DIR = WORK / "sources"
MANIFEST = WORK / "yugo-images-v200.json"

ITEMS = [
    {
        "cardId": "ref-v10-artillery-m15-105",
        "stem": "photo-v200-ref-v10-artillery-m15-105-0",
        "pdf": "yugo_m15bt.pdf",
        "url": "https://www.yugoimport.com/sites/default/files/documents/2024-01/105%20mm,%20WITH%20HEER-BT%20M15%20AND%20FULL%20VARIABLE%20PROPELLANT%20CHARGE%20M15A.pdf",
        "sourceTitle": "Yugoimport — 105 mm with projectile HEER-BT M15 and full variable propellant charge M15A — PDF-стр. 1",
        "caption": "M15 HEER-BT, 105 мм: внешний вид снаряда и полного переменного заряда M15A на официальном листе Yugoimport, PDF-страница 1. Автор изображения и открытая лицензия не указаны. Без увеличения и дорисовки.",
    },
    {
        "cardId": "ref-v10-artillery-m19-155",
        "stem": "photo-v200-ref-v10-artillery-m19-155-0",
        "pdf": "yugo_m19bb.pdf",
        "url": "https://www.yugoimport.com/sites/default/files/documents/2024-02/155%20mm%20WITH%20HEER-BB%20M19%20AND%20PROPELLANT%20CHARGE%20MC%20ZONE%209%20for%20NORA%20B52%20M15.pdf",
        "sourceTitle": "Yugoimport — 155 mm with HEER-BB M19 and propellant charge MC zone 9 — PDF-стр. 1",
        "caption": "M19 HEER-BB, 155 мм: внешний вид снаряда с донным газогенератором и заряда MC zone 9 на официальном листе Yugoimport, PDF-страница 1. Автор изображения и открытая лицензия не указаны. Без увеличения и дорисовки.",
    },
    {
        "cardId": "ref-v10-artillery-m19-155",
        "stem": "photo-v200-ref-v10-artillery-m19-155-1",
        "pdf": "yugo_m19bt.pdf",
        "url": "https://www.yugoimport.com/sites/default/files/documents/2024-02/155%20mm%20WITH%20HEER-BT%20M19%20AND%20PROPELLANT%20CHARGE%20MC%20ZONE%209%20for%20NORA%20B52%20M15.pdf",
        "sourceTitle": "Yugoimport — 155 mm with HEER-BT M19 and propellant charge MC zone 9 — PDF-стр. 1",
        "caption": "M19 HEER-BT, 155 мм: внешний вид снаряда с конической задней частью и заряда MC zone 9 на официальном листе Yugoimport, PDF-страница 1. Автор изображения и открытая лицензия не указаны. Без увеличения и дорисовки.",
    },
    {
        "cardId": "ref-v10-artillery-m79-130",
        "stem": "photo-v200-ref-v10-artillery-m79-130-0",
        "pdf": "yugo_m79.pdf",
        "url": "https://www.yugoimport.com/sites/default/files/documents/2024-02/130%20mm%20WITH%20HE%20M79%20AND%20FULL%20VARIABLE%20PROPELLANT%20CHARGE%20M46%20FOR%20130%20GUN%20M46.pdf",
        "sourceTitle": "Yugoimport — 130 mm with HE M79 and full variable propellant charge M46 — PDF-стр. 1",
        "caption": "M79, 130 мм: внешний вид снаряда и полного переменного заряда M46 на официальном листе Yugoimport, PDF-страница 1. Автор изображения и открытая лицензия не указаны. Без увеличения и дорисовки.",
    },
    {
        "cardId": "ref-v10-artillery-m93-130",
        "stem": "photo-v200-ref-v10-artillery-m93-130-0",
        "pdf": "yugo_m93.pdf",
        "url": "https://www.yugoimport.com/sites/default/files/documents/2024-02/130%20mm%20WITH%20HE%20M93%20AND%20BASE-BLEED%20AND%20FULL%20PROPELLANT%20CHARGE%20M93A%20FOR%20130%20GUN%20M46.pdf",
        "sourceTitle": "Yugoimport — 130 mm with HE M93 with base-bleed and full propellant charge M93A — PDF-стр. 1",
        "caption": "M93, 130 мм: внешний вид снаряда с донным газогенератором и полного заряда M93A на официальном листе Yugoimport, PDF-страница 1. Автор изображения и открытая лицензия не указаны. Без увеличения и дорисовки.",
    },
]


def download(name: str, url: str) -> Path:
    SOURCES_DIR.mkdir(parents=True, exist_ok=True)
    target = SOURCES_DIR / name
    if target.is_file() and target.stat().st_size:
        return target
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    data = urlopen(request, timeout=90).read()
    if not data.startswith(b"%PDF"):
        raise ValueError(f"Not a PDF: {url}")
    target.write_bytes(data)
    return target


def select_product_image(pdf: Path) -> Image.Image:
    reader = PdfReader(str(pdf))
    if len(reader.pages) != 1:
        raise ValueError(f"Expected one-page product sheet: {pdf}")
    candidates = []
    for image in reader.pages[0].images:
        try:
            raster = Image.open(io.BytesIO(image.data)).convert("RGBA")
        except Exception:
            continue
        width, height = raster.size
        if 250 <= width <= 700 and 600 <= height <= 1100 and height / width > 1.45:
            candidates.append(raster)
    if len(candidates) != 1:
        raise ValueError(f"Expected exactly one product raster in {pdf}, got {len(candidates)}")
    raster = candidates[0]
    background = Image.new("RGBA", raster.size, "white")
    return Image.alpha_composite(background, raster).convert("RGB")


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


def upsert_image(card: dict, item: dict, asset: dict) -> None:
    image = {
        "id": item["stem"],
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
        "id": f"source-{item['stem']}",
        "title": f"{card['title']} — официальный оригинал иллюстрации (автор и открытая лицензия не указаны)",
        "url": item["url"],
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
    for item in ITEMS:
        pdf = download(item["pdf"], item["url"])
        raster = select_product_image(pdf)
        asset = save_asset(raster, item["stem"])
        card = cards[item["cardId"]]
        upsert_image(card, item, asset)
        entries.append({**item, **asset, "pdfSha256": hashlib.sha256(pdf.read_bytes()).hexdigest()})
    data["contentVersion"] = TARGET_VERSION
    data["catalogVersion"] = TARGET_VERSION
    PRODUCTION_CATALOG.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (ASSETS / "database/content-version.txt").write_text(f"{TARGET_VERSION}\n", encoding="utf-8")
    counts = build(PRODUCTION_CATALOG, PRODUCTION_DATABASE)
    MANIFEST.write_text(json.dumps({
        "batch": "yugo-official-visuals-v200",
        "generatedAt": TODAY,
        "policy": "Official factory sheet; embedded raster preserved without upscaling or retouching; author/open licence unknown.",
        "entries": entries,
        "build": counts,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"updatedCards": sorted({item["cardId"] for item in ITEMS}),
                      "addedImages": len(ITEMS), "build": counts}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
