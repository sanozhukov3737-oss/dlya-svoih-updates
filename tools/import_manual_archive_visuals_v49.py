#!/usr/bin/env python3
"""Import exact recognition visuals from four open U.S. government manuals.

Only the identifying heading and exterior/recognition figure are rendered.  The
operational prose in the manuals is deliberately excluded from the asset crop.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import fitz
from PIL import Image, ImageChops, ImageOps


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "app/src/main/assets"
CATALOG_IN = ROOT / "content/catalog-v45-pass02.json"
AUDIT_IN = ROOT / "content/audit/photo-audit-v45-pass02.json"
CATALOG_OUT = ROOT / "content/catalog-v46-pass01.json"
AUDIT_OUT = ROOT / "content/audit/photo-audit-v46-pass01.json"
SEARCH_OUT = ROOT / "content/audit/photo-search-v46-pass01.json"
MANIFEST_OUT = ROOT / "content/audit/visual-batch-v46-pass01-manifest.json"

TODAY = "2026-09-19"
PASS = "v46-pass01"

SOURCES = {
    "tm28": {
        "filename": "tm_43-0001-28_army_ammunition_data_sheets.pdf",
        "title": "TM 43-0001-28 — Army Ammunition Data Sheets",
        "pageUrl": "https://archive.org/details/milmanual-tm-43-0001-28-army-ammunition-data-sheets",
        "directUrl": "https://archive.org/download/milmanual-tm-43-0001-28-army-ammunition-data-sheets/tm_43-0001-28_army_ammunition_data_sheets.pdf",
        "rights": "public-domain-us-government-manual",
    },
    "tm36": {
        "filename": "tm-43-0001-36_ammunition_data_sheets_for_land_mines.pdf",
        "title": "TM 43-0001-36 — Army Ammunition Data Sheets for Land Mines",
        "pageUrl": "https://archive.org/details/milmanual-tm-43-0001-36-ammunition-data-sheets-for-land-mines",
        "directUrl": "https://archive.org/download/milmanual-tm-43-0001-36-ammunition-data-sheets-for-land-mines/tm-43-0001-36_ammunition_data_sheets_for_land_mines.pdf",
        "rights": "public-domain-us-government-manual",
    },
    "aoig": {
        "filename": "aoig.pdf",
        "title": "Afghanistan Ordnance Identification Guide — Naval EOD Technology Division, 2004",
        "pageUrl": "https://archive.org/details/afghanistan-ordnance-identification-guide-volume-1",
        "directUrl": "https://archive.org/download/afghanistan-ordnance-identification-guide-volume-1/Afghanistan%20Ordnance%20Identification%20Guide%2C%20Volume%201.pdf",
        "rights": "official-us-government-humanitarian-identification-guide",
    },
    "iraq": {
        "filename": "iraq-oig.pdf",
        "title": "Iraq Ordnance Identification Guide — U.S. DoD Humanitarian Mine Action Program",
        "pageUrl": "https://www.jmu.edu/cisr/research/iraq-oig/index.shtml",
        "directUrl": "https://www.bulletpicker.com/pdf/ID-Guide-Iraq.pdf",
        "rights": "official-us-government-humanitarian-identification-guide",
    },
}


def item(card_id: str, stem: str, source: str, page: int,
         crop: tuple[float, float, float, float], caption: str) -> dict:
    return {
        "cardId": card_id,
        "stem": stem,
        "source": source,
        "page": page,
        "crop": crop,
        "caption": caption,
    }


ITEMS = [
    item("ordnance-v29-ga-0483", "manual-v49-m900", "tm28", 110, (0.00, 0.00, 1.00, 0.34),
         "105-мм выстрел M900: точная техническая иллюстрация TM 43-0001-28; это не фотография."),
    item("ordnance-v29-ga-0243", "manual-v49-m768", "tm28", 412, (0.00, 0.00, 1.00, 0.42),
         "60-мм миномётный выстрел M768: точная техническая иллюстрация TM 43-0001-28; это не фотография."),
    item("ordnance-v29-ga-0214", "manual-v49-m934a1", "tm28", 518, (0.00, 0.00, 1.00, 0.38),
         "120-мм миномётный выстрел M934A1: точная техническая иллюстрация TM 43-0001-28; это не фотография."),
    item("ordnance-v29-ga-0147", "manual-v49-m922a1", "tm28", 628, (0.00, 0.00, 1.00, 0.37),
         "40-мм учебный выстрел M922A1: точная техническая иллюстрация TM 43-0001-28; это не фотография."),
    item("ordnance-v27-m74-subboepripas", "manual-v49-m74", "tm36", 42, (0.00, 0.00, 1.00, 0.42),
         "Мина-суббоеприпас M74: точный внешний вид из TM 43-0001-36; это техническая иллюстрация."),
    item("ordnance-v27-m131-mopms-sistema-rasseivaniya-min", "manual-v49-m131", "tm36", 124, (0.00, 0.00, 1.00, 0.50),
         "Система M131 MOPMS: точная техническая иллюстрация штатного диспенсера из TM 43-0001-36."),
    item("ordnance-v27-ym-ii-iran", "manual-v49-ym2", "aoig", 139, (0.00, 0.47, 1.00, 0.96),
         "Иранская противотанковая мина YM-II: точный подписанный визуал Afghanistan Ordnance Identification Guide."),
    item("ordnance-v27-m-6-vzryvatel", "manual-v49-m6-fuze", "aoig", 264, (0.00, 0.46, 1.00, 0.96),
         "Артиллерийский взрыватель М-6: точный подписанный визуал Afghanistan Ordnance Identification Guide."),
    item("ordnance-v27-t-7-vzryvatel", "manual-v49-t7-fuze", "aoig", 310, (0.00, 0.45, 1.00, 0.96),
         "Советский артиллерийский взрыватель Т-7: точный подписанный визуал Afghanistan Ordnance Identification Guide."),
    item("ordnance-v27-120-mm-of-843", "manual-v49-of843", "aoig", 432, (0.00, 0.00, 1.00, 0.52),
         "120-мм миномётная мина ОФ-843: точный подписанный визуал Afghanistan Ordnance Identification Guide."),
    item("ordnance-v27-pg-18", "manual-v49-pg18", "aoig", 215, (0.00, 0.00, 1.00, 0.52),
         "Реактивная противотанковая граната ПГ-18: точный подписанный визуал Afghanistan Ordnance Identification Guide."),
    item("ordnance-v27-82-mm-o-832", "manual-v49-o832", "iraq", 181, (0.00, 0.00, 1.00, 0.53),
         "82-мм миномётная мина О-832: точный подписанный визуал Iraq Ordnance Identification Guide."),
    item("ordnance-v27-tm-120-vzryvatel", "manual-v49-tm120-fuze", "iraq", 431, (0.00, 0.46, 1.00, 0.96),
         "Ракетный взрыватель ТМ-120: точный подписанный визуал Iraq Ordnance Identification Guide."),
    item("ordnance-v27-atm-6-kndr", "manual-v49-atm6", "iraq", 596, (0.00, 0.47, 1.00, 0.96),
         "Австрийская противотанковая мина ATM-6: точный подписанный визуал Iraq Ordnance Identification Guide."),
    item("ordnance-v27-ym-iii-ym-3-iran", "manual-v49-ym3", "iraq", 604, (0.00, 0.00, 1.00, 0.52),
         "Иранская противотанковая мина YM-III: точный визуал одного из прямо перечисленных обозначений объединённой карточки YM-III / YM-3."),
    item("mine-audit-v25-cs-pt-mi-ba-iii", "manual-v49-ptmiba3", "iraq", 609, (0.00, 0.47, 1.00, 0.96),
         "Чехословацкая PT-MI-BA III: точный подписанный визуал Iraq Ordnance Identification Guide."),
]


def trim_white(image: Image.Image) -> Image.Image:
    gray = ImageOps.grayscale(image)
    diff = ImageChops.difference(gray, Image.new("L", gray.size, 255))
    mask = diff.point(lambda value: 255 if value > 18 else 0)
    box = mask.getbbox()
    if not box:
        return image
    pad = 24
    return image.crop((max(0, box[0] - pad), max(0, box[1] - pad),
                       min(image.width, box[2] + pad), min(image.height, box[3] + pad)))


def render(pdf: Path, page_number: int, crop: tuple[float, float, float, float], stem: str) -> dict:
    document = fitz.open(pdf)
    try:
        page = document[page_number - 1]
        rect = page.rect
        clip = fitz.Rect(rect.x0 + rect.width * crop[0], rect.y0 + rect.height * crop[1],
                         rect.x0 + rect.width * crop[2], rect.y0 + rect.height * crop[3])
        pixmap = page.get_pixmap(matrix=fitz.Matrix(2.25, 2.25), clip=clip, alpha=False)
        image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
    finally:
        document.close()
    image = trim_white(image)
    image.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
    full_rel = f"images/{stem}.webp"
    thumb_rel = f"thumbs/{stem}.webp"
    full = ASSETS / full_rel
    thumb = ASSETS / thumb_rel
    full.parent.mkdir(parents=True, exist_ok=True)
    thumb.parent.mkdir(parents=True, exist_ok=True)
    image.save(full, "WEBP", quality=88, method=6)
    miniature = image.copy()
    miniature.thumbnail((256, 256), Image.Resampling.LANCZOS)
    miniature.save(thumb, "WEBP", quality=84, method=6)
    return {"localPath": full_rel, "thumbnailPath": thumb_rel,
            "width": image.width, "height": image.height}


def write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(sources_dir: Path) -> None:
    catalog = json.loads(CATALOG_IN.read_text(encoding="utf-8"))
    audit = json.loads(AUDIT_IN.read_text(encoding="utf-8"))
    if (catalog.get("contentVersion"), catalog.get("catalogVersion")) != (45, "v45-pass02"):
        raise RuntimeError("Expected v45-pass02 input catalog")
    cards = {card["id"]: card for card in catalog["cards"]}
    rows = {row["cardId"]: row for row in audit["rows"]}
    source_files = {}
    source_manifest = {}
    for key, metadata in SOURCES.items():
        pdf = sources_dir / metadata["filename"]
        if not pdf.is_file():
            raise FileNotFoundError(pdf)
        source_files[key] = pdf
        source_manifest[key] = {
            **metadata,
            "bytes": pdf.stat().st_size,
            "sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(),
            "pages": len(fitz.open(pdf)),
        }

    entries = []
    for spec in ITEMS:
        card = cards[spec["cardId"]]
        if card.get("images"):
            raise RuntimeError(f"Card already has an image: {spec['cardId']}")
        source = SOURCES[spec["source"]]
        asset = render(source_files[spec["source"]], spec["page"], spec["crop"], spec["stem"])
        image = {
            "id": spec["stem"], **asset, "caption": spec["caption"],
            "position": 0, "mediaType": "official-government-manual-recognition-illustration",
        }
        card["images"] = [image]
        source_id = f"src-{spec['stem']}"
        card["sources"].append({
            "id": source_id,
            "title": f"{source['title']}, физическая страница PDF {spec['page']}",
            "url": f"{source['pageUrl']}#page={spec['page']}",
            "accessedAt": TODAY,
        })
        card["body"] += (
            "\n\n## Визуал из открытого руководства\n\n"
            + spec["caption"]
            + " В карточку включён только опознавательный фрагмент без инструкций по применению или обезвреживанию."
        )
        card["tags"] = list(dict.fromkeys(card.get("tags", []) + ["точный визуал", "официальное руководство", "визуал v49"]))
        card["reviewedAt"] = TODAY
        card["verifiedAt"] = TODAY

        row = rows[spec["cardId"]]
        row.update({
            "searchedAt": TODAY,
            "exactImageLocated": True,
            "mediaType": image["mediaType"],
            "sourcePageUrl": f"{source['pageUrl']}#page={spec['page']}",
            "directImageUrl": source["directUrl"],
            "licenseStatus": source["rights"],
            "reuseDecision": "bundled",
            "localPath": asset["localPath"],
            "searchOutcome": "Точная модель найдена в открытом официальном руководстве; встроен только опознавательный фрагмент листа.",
            "lastSearchPass": PASS,
            "credit": source["title"],
            "visualCoverage": "exact",
            "photoEligibility": "exact-visual-bundled",
            "actionablePhotoSearch": False,
            "sourcePdfPhysicalPage": spec["page"],
        })
        entries.append({
            "cardId": spec["cardId"], "title": card["title"], "visualCoverage": "exact",
            "sourceKey": spec["source"], "sourcePdfPhysicalPage": spec["page"],
            "crop": spec["crop"], "image": image, "source": card["sources"][-1],
            "licenseStatus": source["rights"],
        })

    catalog["contentVersion"] = 46
    catalog["catalogVersion"] = PASS
    write(CATALOG_OUT, catalog)
    write(ROOT / "content/catalog.json", catalog)

    audit["auditVersion"] = PASS
    audit["generatedAt"] = TODAY
    audit["scope"] = "Каталог v46-pass01; 16 точных визуалов из четырёх открытых официальных руководств США."
    summary = audit["summary"]
    summary.update({
        "catalogCards": len(catalog["cards"]),
        "exactImagesLocated": sum(row.get("exactImageLocated") is True for row in audit["rows"]),
        "bundledImages": sum(str(row.get("reuseDecision", "")).startswith("bundled") for row in audit["rows"]),
        "unresolvedRows": sum(row.get("exactImageLocated") is not True for row in audit["rows"]),
        "rightsBlockedRows": sum(row.get("exactImageLocated") is True and row.get("reuseDecision") == "not-bundled" for row in audit["rows"]),
        "catalogCardsWithImages": sum(bool(card.get("images")) for card in catalog["cards"]),
        "catalogCardsWithoutImages": sum(not card.get("images") for card in catalog["cards"]),
        "actionablePhotoRowsRemaining": sum(row.get("actionablePhotoSearch") is True and row.get("exactImageLocated") is not True for row in audit["rows"]),
        "v46Pass01ManualsReviewed": len(SOURCES),
        "v46Pass01ExactVisualsBundled": len(ITEMS),
        "v46CardsWithoutImages": sum(not card.get("images") for card in catalog["cards"]),
    })
    write(AUDIT_OUT, audit)
    write(SEARCH_OUT, {
        "version": PASS, "generatedAt": TODAY,
        "policy": "Только точное обозначение на официальном листе; в asset входит заголовок и внешний опознавательный визуал, без операционного текста.",
        "summary": {
            "manualsReviewed": len(SOURCES), "rowsReviewed": len(ITEMS),
            "exactVisualsBundled": len(ITEMS), "familyVisualsBundled": 0,
            "copyrightedThirdPartyVisualsCopied": 0,
            "catalogCardsWithImages": summary["catalogCardsWithImages"],
            "catalogCardsWithoutImages": summary["catalogCardsWithoutImages"],
        },
        "rows": [rows[item["cardId"]] for item in ITEMS],
    })
    write(MANIFEST_OUT, {
        "batchId": "manual-archives-v49-pass01", "generatedAt": TODAY,
        "policy": "Exact designation only; recognition crop only; no procedural text bundled.",
        "sources": source_manifest, "entries": entries,
    })
    print(f"Imported {len(ITEMS)} exact manual visuals")
    print(f"Cards without images: {summary['catalogCardsWithoutImages']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--sources-dir", type=Path, required=True)
    args = parser.parse_args()
    main(args.sources_dir)
