#!/usr/bin/env python3
"""Add reviewed openly-licensed Wikimedia Commons images for catalog 201.

Every image was visually verified against the card item, its Commons file page
carries an open licence (CC BY / CC BY-SA / public domain), and the author is
recorded in the caption and source. Files larger than the Android limit are
downscaled to 1600 px on the long side; no retouching.
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
TODAY = "2026-10-31"
TARGET_VERSION = 201
WORK = ROOT / "build/catalog201-commons"
MANIFEST = WORK / "commons-images-v201.json"

ITEMS = [
    {
        "cardId": "pdf198-5-8c56ae01689c",
        "file": "BM-27 Uragan ammunition.jpg",
        "license": "CC BY 4.0",
        "artist": "F.Alexsandr",
        "page": "https://commons.wikimedia.org/wiki/File:BM-27_Uragan_ammunition.jpg",
        "caption": "220-мм реактивные снаряды системы «Ураган» в транспортно-пусковых контейнерах, музейная экспозиция. Автор: F.Alexsandr, Wikimedia Commons, CC BY 4.0.",
    },
    {
        "cardId": "pdf198-5-c1eeb33072c7",
        "file": "Rocket from BM-27 Uragan in Babai, Kharkiv Oblast (1).jpg",
        "license": "CC BY 4.0",
        "artist": "ГСЧС Украины",
        "page": "https://commons.wikimedia.org/wiki/File:Rocket_from_BM-27_Uragan_in_Babai,_Kharkiv_Oblast_(1).jpg",
        "caption": "Хвостовая часть 220-мм реактивного снаряда системы «Ураган» с маркировкой «9М27»; обнаруженный снаряд, Харьковская область. Автор: ГСЧС Украины, Wikimedia Commons, CC BY 4.0.",
    },
    {
        "cardId": "pdf198-2-e6d20e202020",
        "file": "PG-29V Antiarmor & TBG-29V Thermobaric Granats Army-2022 2022-08-20 2236.jpg",
        "license": "CC BY-SA 4.0",
        "artist": "Mike1979 Russia",
        "page": "https://commons.wikimedia.org/wiki/File:PG-29V_Antiarmor_%26_TBG-29V_Thermobaric_Granats_Army-2022_2022-08-20_2236.jpg",
        "caption": "Макеты выстрелов ПГ-29В (сверху) и ТБГ-29В на выставке «Армия-2022». Автор: Mike1979 Russia, Wikimedia Commons, CC BY-SA 4.0.",
    },
    {
        "cardId": "pdf198-2-7ae2c2cd13e2",
        "file": "TBG-29V Thermobaric Granat Army-2022 2022-08-20 2237.jpg",
        "license": "CC BY-SA 4.0",
        "artist": "Mike1979 Russia",
        "page": "https://commons.wikimedia.org/wiki/File:TBG-29V_Thermobaric_Granat_Army-2022_2022-08-20_2237.jpg",
        "caption": "Макет выстрела ТБГ-29В на выставке «Армия-2022». Автор: Mike1979 Russia, Wikimedia Commons, CC BY-SA 4.0.",
    },
    {
        "cardId": "pdf198-2-a746fec3638b",
        "file": "Rpg-26.jpg",
        "license": "CC BY-SA 4.0",
        "artist": "Historiador09NI",
        "page": "https://commons.wikimedia.org/wiki/File:Rpg-26.jpg",
        "caption": "РПГ-26 с выстрелом и тренировочным устройством. Автор: Historiador09NI, Wikimedia Commons, CC BY-SA 4.0.",
    },
    {
        "cardId": "pdf198-2-a746fec3638b",
        "file": "Grenade launchers RPG-26.jpg",
        "license": "Public domain",
        "artist": "Sergeev Pavel",
        "page": "https://commons.wikimedia.org/wiki/File:Grenade_launchers_RPG-26.jpg",
        "caption": "РПГ-26 в экспозиции Вологодского музея милиции. Автор: Sergeev Pavel, Wikimedia Commons, общественное достояние.",
    },
    {
        "cardId": "pdf198-2-36e0ff64653b",
        "file": "МРК-27 БТ с РШГ-2 и РПО Шмель - Интерполитех-2009 01.jpg",
        "license": "CC BY-SA 4.0",
        "artist": "Vitaly V. Kuzmin",
        "page": "https://commons.wikimedia.org/wiki/File:%D0%9C%D0%A0%D0%9A-27_%D0%91%D0%A2_%D1%81_%D0%A0%D0%A8%D0%93-2_%D0%B8_%D0%A0%D0%9F%D0%9E_%D0%A8%D0%BC%D0%B5%D0%BB%D1%8C_-_%D0%98%D0%BD%D1%82%D0%B5%D1%80%D0%BF%D0%BE%D0%BB%D0%B8%D1%82%D0%B5%D1%85-2009_01.jpg",
        "caption": "Мобильный роботизированный комплекс МРК-27БТ с РШГ-2 и РПО «Шмель», выставка «Интерполитех-2009». Автор: Vitaly V. Kuzmin, Wikimedia Commons, CC BY-SA 4.0.",
    },
    {
        "cardId": "pdf198-7-c23b45f8ab93",
        "file": "H. Dv. 211-2, Nebelhandgranate 39.png",
        "license": "Public domain",
        "artist": "Oberbefehlshaber des Heeres",
        "page": "https://commons.wikimedia.org/wiki/File:H._Dv._211-2,_Nebelhandgranate_39.png",
        "caption": "Nebelhandgranate 39 — рисунок из наставления H.Dv. 211/2 «Die Nebelhandgranate 39» (1939). Общественное достояние.",
    },
    {
        "cardId": "pdf198-7-c23b45f8ab93",
        "file": "H. Dv. 211-2, Nebelhandgranate 39, Brennzünder 39.png",
        "license": "Public domain",
        "artist": "Oberbefehlshaber des Heeres",
        "page": "https://commons.wikimedia.org/wiki/File:H._Dv._211-2,_Nebelhandgranate_39,_Brennz%C3%BCnder_39.png",
        "caption": "Brennzünder 39 — воспламенитель дымовой гранаты; рисунок из наставления H.Dv. 211/2 (1939). Общественное достояние.",
    },
    {
        "cardId": "pdf198-7-c23b45f8ab93",
        "file": "Merkblatt 68-16-Bildheft 148, Nebelhandgranate 39.png",
        "license": "Public domain",
        "artist": "Oberkommando des Heeres",
        "page": "https://commons.wikimedia.org/wiki/File:Merkblatt_68-16-Bildheft_148,_Nebelhandgranate_39.png",
        "caption": "Nebelhandgranate 39 — фотография из памятки Merkblatt 68/16, Bildheft 148. Общественное достояние.",
    },
    {
        "cardId": "pdf198-7-780caa4a776c",
        "file": "Rifle grenade launcher Mosin-Nagant 2.JPG",
        "license": "Public domain",
        "artist": "MKFI",
        "page": "https://commons.wikimedia.org/wiki/File:Rifle_grenade_launcher_Mosin-Nagant_2.JPG",
        "caption": "Винтовка Мосина с кубовидной гранатомортирой для стрельбы ружейными гранатами (класс гранатомёта Дьяконова), музейная экспозиция. Автор: MKFI, Wikimedia Commons, общественное достояние.",
    },
    {
        "cardId": "pdf198-8-32d925f508bc",
        "file": "Chaklun UAV and Destinus cruise missile at IDEX 2025.jpg",
        "license": "CC BY 4.0",
        "artist": "Mztourist",
        "page": "https://commons.wikimedia.org/wiki/File:Chaklun_UAV_and_Destinus_cruise_missile_at_IDEX_2025.jpg",
        "caption": "БПЛА-камикадзе «Чаклун» и крылатая ракета Destinus на стенде «Спецтехноэкспорта», выставка IDEX-2025. Автор: Mztourist, Wikimedia Commons, CC BY 4.0.",
    },
    {
        "cardId": "pdf198-8-1b149030858b",
        "file": "Aeroprakt.a22.foxbat.arp.jpg",
        "license": "Public domain",
        "artist": "Arpingstone",
        "page": "https://commons.wikimedia.org/wiki/File:Aeroprakt.a22.foxbat.arp.jpg",
        "caption": "Базовый самолёт Aeroprakt A-22 «Foxbat», на котором построен дрон-камикадзе А-22 «Летучая лисица». Автор: Arpingstone, Wikimedia Commons, общественное достояние.",
    },
    {
        "cardId": "pdf198-8-bbbe911a97eb",
        "file": "Ukraine Palianytsia.png",
        "license": "CC BY-SA 4.0",
        "artist": "पाटलिपुत्र",
        "page": "https://commons.wikimedia.org/wiki/File:Ukraine_Palianytsia.png",
        "caption": "Схематичное изображение дрон-ракеты «Паляниця». Автор: पाटलिपुत्र, Wikimedia Commons, CC BY-SA 4.0.",
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
        stem = f"photo-v201-{short}-{index}"
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
        "batch": "commons-open-license-v201",
        "generatedAt": TODAY,
        "policy": "Wikimedia Commons files with open licences (CC BY / CC BY-SA / public domain); visually verified against the card item; downscaled to 1600 px max, no retouching.",
        "entries": entries,
        "build": counts,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"updatedCards": sorted({item["cardId"] for item in ITEMS}),
                      "addedImages": len(ITEMS), "build": counts}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
