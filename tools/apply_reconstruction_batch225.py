#!/usr/bin/env python3
"""Add 34 owner-approved exterior reconstructions (catalog 225)."""
from __future__ import annotations
import hashlib, json
from pathlib import Path
from PIL import Image
from build_catalog import PRODUCTION_CATALOG, PRODUCTION_DATABASE, ASSETS, build

ROOT = Path(__file__).resolve().parents[1]
TODAY = "2026-11-02"
VERSION = 225
BANK = ROOT.parent / "aosearch/v225_reconstructions"
WORK = ROOT / "build/catalog225-reconstruction-batch"
U28 = "https://www.bulletpicker.com/pdf/TM-43-0001-28-1994.pdf"
NAMMO = "https://www.nammo.com/wp-content/uploads/2024/09/Nammo-Handbook-2024_08_Web.cleaned.pdf"
KS19 = "https://sprotyvg7.com.ua/wp-content/uploads/2023/07/%D0%9A%D0%A1-19.pdf"
SAPPER = "https://sprotyvg7.com.ua/wp-content/uploads/2023/08/%D0%90%D0%BB%D1%8C%D0%B1%D0%BE%D0%BC-%D1%81%D0%B0%D0%BF%D1%91%D1%80%D0%B0-%D0%BC%D0%B8%D0%BD%D1%91%D1%80%D0%B0.pdf"

ITEMS = [
    ("ordnance-v29-ga-0223", "120 мм M930", "m930", 530, U28),
    ("ordnance-v29-ga-0406", "120 мм IM Canister", "nammo-120mm-im-canister", 117, NAMMO),
    ("pdf198-5-902b39a490a2", "100-мм выстрел УОФ-412", "uof412", 24, KS19),
    ("pdf198-5-f2b2ab1417b7", "100-мм выстрел УБР-412Б", "ubr412b", 25, KS19),
    ("pdf198-5-32804f822afc", "100-мм выстрел УБР-412Д", "ubr412d", 25, KS19),
    ("pdf198-5-96ac11cfe0f3", "100-мм выстрел УОФ10", "uof10", 86, KS19),
    ("pdf198-5-456205fe3143", "122-мм выстрел ВОФ5", "vof5", 78, SAPPER),
    ("pdf198-5-baadd77f3031", "122-мм выстрел ВОФ6", "vof6", 78, SAPPER),
    ("pdf198-5-279ca196a52e", "122-мм выстрел ВОФ14", "vof14", 79, SAPPER),
    ("pdf198-5-70f55ebb6d67", "122-мм выстрел ВОФ29", "vof29", 79, SAPPER),
    ("pdf198-5-638100261666", "122-мм выстрел ВОФ30", "vof30", 80, SAPPER),
    ("pdf198-5-1e24cfc5d480", "122-мм выстрел ВБК12", "vbk12", 80, SAPPER),
    ("pdf198-5-733794207681", "125-мм выстрел ВОФ22", "vof22", 81, SAPPER),
    ("pdf198-5-776f3d8a674e", "152-мм выстрел ВОФ-546У", "vof546u", 85, SAPPER),
    ("pdf198-5-81fa887453ef", "152-мм выстрел ВОФ32", "vof32", 85, SAPPER),
    ("pdf198-5-e1e4ab956b02", "152-мм выстрел ВОФ32-1", "vof32-1", 86, SAPPER),
    ("pdf198-5-0f239600ca97", "152-мм выстрел ВОФ33", "vof33", 86, SAPPER),
    ("pdf198-5-3d20afd353ab", "152-мм выстрел ВОФ33-1", "vof33-1", 87, SAPPER),
    ("pdf198-5-cd7952d448ba", "37-мм выстрел УОР-167", "uor167", 97, SAPPER),
    ("pdf198-5-5acb2eeca9af", "37-мм выстрел УОР-167Н", "uor167n", 98, SAPPER),
    ("pdf198-5-2ccae3f3c0d2", "37-мм выстрел УБР-167", "ubr167", 98, SAPPER),
    ("pdf198-5-7f77eb5f00ce", "57-мм выстрел УО-271УЖ", "uo271uzh", 99, SAPPER),
    ("pdf198-5-1dd48173bdd1", "57-мм выстрел УБР-271М", "ubr271m", 100, SAPPER),
    ("pdf198-5-017bfda88263", "100-мм выстрел УО-415", "uo415", 101, SAPPER),
    ("pdf198-5-99d8cacad727", "82-мм выстрел ВО-832Д", "vo832d", 102, SAPPER),
    ("pdf198-5-d94533196c5a", "82-мм выстрел ВО-832С", "vo832s", 102, SAPPER),
    ("pdf198-5-dbe015390299", "82-мм выстрел ВО1", "vo1", 103, SAPPER),
    ("pdf198-5-e87aed7372ac", "82-мм выстрел ВО12", "vo12", 103, SAPPER),
    ("pdf198-5-706991de109d", "82-мм выстрел ВО18", "vo18", 104, SAPPER),
    ("pdf198-5-f45bab7755b8", "120-мм выстрел ВОФ-843А", "vof843a", 107, SAPPER),
    ("pdf198-5-352a97758b21", "120-мм выстрел ВОФ-843АУ", "vof843au", 108, SAPPER),
    ("pdf198-5-337906c26a17", "120-мм выстрел ВОФ-843Б", "vof843b", 108, SAPPER),
    ("pdf198-5-9d0245a0f49a", "120-мм выстрел ВОФ-843", "vof843", 109, SAPPER),
    ("pdf198-5-17bd823ef05c", "120-мм выстрел ВОФ-843У", "vof843u", 109, SAPPER),
]


def main():
    WORK.mkdir(parents=True, exist_ok=True)
    data = json.loads(PRODUCTION_CATALOG.read_text(encoding="utf-8"))
    cards = {c["id"]: c for c in data["cards"]}
    entries = []
    for card_id, title, slug, page, url in ITEMS:
        stem = f"reconstruction-v225-{slug.replace('_', '-')}"
        card = cards[card_id]
        if any(not x["id"].startswith("reconstruction-v225-") for x in card["images"]):
            raise RuntimeError(f"Unexpected existing image: {card_id}")
        raster = Image.open(BANK / f"{slug}.png").convert("RGB")
        raster.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
        full_rel, thumb_rel = f"images/{stem}.webp", f"thumbs/{stem}.webp"
        full, thumb = ASSETS / full_rel, ASSETS / thumb_rel
        raster.save(full, "WEBP", quality=90, method=6)
        miniature = raster.copy()
        miniature.thumbnail((256, 256), Image.Resampling.LANCZOS)
        miniature.save(thumb, "WEBP", quality=84, method=6)
        card["images"] = [{
            "id": stem,
            "localPath": full_rel,
            "caption": f"{title} — иллюстративная реконструкция внешнего вида по открытому пособию, PDF-страница {page}. Не фотография и не рабочий чертёж; маркировка и клейма не воспроизводятся.",
            "width": raster.width,
            "height": raster.height,
            "position": 0,
            "thumbnailPath": thumb_rel,
        }]
        card["thumbnailPath"] = thumb_rel
        source = {
            "id": f"source-{stem}",
            "title": f"{title} — открытое пособие, PDF-страница {page}; исходная схема в каталог не копировалась",
            "url": url,
            "accessedAt": TODAY,
        }
        card["sources"] = [x for x in card["sources"] if not x["id"].startswith("source-reconstruction-v225-")] + [source]
        entries.append({
            "cardId": card_id,
            "imageId": stem,
            "fullSha256": hashlib.sha256(full.read_bytes()).hexdigest(),
            "thumbnailSha256": hashlib.sha256(thumb.read_bytes()).hexdigest(),
            "license": "Original AI-assisted illustrative reconstruction; no source image redistributed",
            "sourceReference": url,
            "sourcePage": page,
            "status": "Approved by owner",
        })
    data["contentVersion"] = data["catalogVersion"] = VERSION
    PRODUCTION_CATALOG.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (ASSETS / "database/content-version.txt").write_text(f"{VERSION}\n", encoding="utf-8")
    counts = build(PRODUCTION_CATALOG, PRODUCTION_DATABASE)
    (WORK / "reconstruction-batch-v225.json").write_text(json.dumps({
        "batch": "original-reconstruction-batch-v225",
        "generatedAt": TODAY,
        "entries": entries,
        "build": counts,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"added": len(entries), "build": counts}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
