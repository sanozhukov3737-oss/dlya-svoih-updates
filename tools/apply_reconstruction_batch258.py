#!/usr/bin/env python3
"""Add five owner-approved exterior reconstructions to previously empty cards (catalog 258)."""
import hashlib
import json
from pathlib import Path
from PIL import Image
from build_catalog import PRODUCTION_CATALOG, PRODUCTION_DATABASE, ASSETS, build

ROOT = Path(__file__).resolve().parents[1]
AOSEARCH = ROOT.parent / 'aosearch'
VERSION = 258
TODAY = '2026-11-03'
WORK = ROOT / 'build/catalog258-reconstruction-batch'
GICHD_TITLE = 'GICHD — Explosive Ordnance Guide for Ukraine, четвёртая редакция, локальная проверенная копия'
MINY_URL = 'https://sprotyvg7.com.ua/wp-content/uploads/2023/01/%D0%9C%D1%96%D0%BD%D0%B8_%D0%9F%D0%BE%D1%81%D1%96%D0%B1%D0%BD%D0%B8%D0%BA_%D0%B2%D1%96%D0%B9%D1%81%D1%8C%D0%BA%D0%BE%D0%B2%D0%BE%D1%81%D0%BB%D1%83%D0%B6%D0%B1%D0%BE%D0%B2%D1%86%D1%8E.pdf'
MINY_TITLE = 'Міни. Посібник військовослужбовцю ЗСУ, НГУ, ДСНС України'
ITEMS = [
    ('pdf198-5-9f57772da9c7', 'v429v', None, GICHD_TITLE + ', PDF-стр. 835'),
    ('pdf198-4-a1be4031ff0d', 'mv62', MINY_URL, MINY_TITLE + ', PDF-стр. 26, объект МВ-62 в правом нижнем углу'),
    ('pdf198-4-2984eccc0742', 'mvd62', MINY_URL, MINY_TITLE + ', PDF-стр. 27, МВД-62 слева на рис. 1.4.5'),
    ('pdf198-4-c8ad27cc7e53', 'vt17', MINY_URL, MINY_TITLE + ', PDF-стр. 27, рис. 1.4.6'),
    ('pdf198-4-ddf3ad5f9809', 'vr04', None, 'Локальная проверенная карточка «Взрыватель ВР-04», внешний вид, PDF-стр. 1'),
]


def main():
    WORK.mkdir(parents=True, exist_ok=True)
    data = json.loads(PRODUCTION_CATALOG.read_text(encoding='utf-8'))
    cards = {card['id']: card for card in data['cards']}
    entries = []
    for card_id, name, source_url, source_title in ITEMS:
        card = cards[card_id]
        title = card['title']
        stem = f'reconstruction-v258-{name}'
        if card['images'] and any(image['id'] != stem for image in card['images']):
            raise RuntimeError(f'Refusing to replace existing image: {card_id}')
        card['sources'] = [source for source in card['sources'] if source['id'] != f'source-{stem}']
        with Image.open(AOSEARCH / f'v258_reconstructions/{name}.png') as source:
            raster = source.convert('RGB')
        raster.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
        full_rel = f'images/{stem}.webp'
        thumb_rel = f'thumbs/{stem}.webp'
        full = ASSETS / full_rel
        thumb = ASSETS / thumb_rel
        raster.save(full, 'WEBP', quality=90, method=6)
        miniature = raster.copy()
        miniature.thumbnail((256, 256), Image.Resampling.LANCZOS)
        miniature.save(thumb, 'WEBP', quality=84, method=6)
        card['images'] = [{
            'id': stem,
            'localPath': full_rel,
            'caption': f'{title} — иллюстративная реконструкция только внешнего вида по открытому референсу. Не фотография и не рабочий чертёж; внутреннее устройство, маркировка, надписи, логотипы и водяные знаки не воспроизводятся.',
            'width': raster.width,
            'height': raster.height,
            'position': 0,
            'thumbnailPath': thumb_rel,
        }]
        card['thumbnailPath'] = thumb_rel
        card['sources'].append({
            'id': f'source-{stem}',
            'title': f'{title} — {source_title}; исходное изображение в каталог не копировалось',
            'url': source_url,
            'accessedAt': TODAY,
        })
        entries.append({
            'cardId': card_id,
            'imageId': stem,
            'fullSha256': hashlib.sha256(full.read_bytes()).hexdigest(),
            'thumbnailSha256': hashlib.sha256(thumb.read_bytes()).hexdigest(),
            'license': 'AI-assisted original illustrative exterior reconstruction based on open references',
            'sourceReference': source_url,
            'sourcePage': 0,
            'status': 'Approved by owner',
        })
    data['contentVersion'] = data['catalogVersion'] = VERSION
    PRODUCTION_CATALOG.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (ASSETS / 'database/content-version.txt').write_text(f'{VERSION}\n', encoding='utf-8')
    counts = build(PRODUCTION_CATALOG, PRODUCTION_DATABASE)
    (WORK / 'reconstruction-batch-v258.json').write_text(json.dumps({
        'batch': 'original-reconstruction-batch-v258',
        'generatedAt': TODAY,
        'entries': entries,
        'build': counts,
    }, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'added': len(entries), 'remainingEmpty': sum(not card['images'] for card in data['cards']), 'build': counts}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
