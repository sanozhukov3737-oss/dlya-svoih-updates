#!/usr/bin/env python3
"""Add six owner-approved exterior reconstructions to previously empty cards (catalog 257)."""
import hashlib
import json
from pathlib import Path
from PIL import Image
from build_catalog import PRODUCTION_CATALOG, PRODUCTION_DATABASE, ASSETS, build

ROOT = Path(__file__).resolve().parents[1]
AOSEARCH = ROOT.parent / 'aosearch'
VERSION = 257
TODAY = '2026-11-03'
WORK = ROOT / 'build/catalog257-reconstruction-batch'
GICHD_TITLE = 'GICHD — Explosive Ordnance Guide for Ukraine, четвёртая редакция, локальная проверенная копия'
KOPANINA_URL = None
ITEMS = [
    ('pdf198-5-5a1a64640b80', 'mrvu', None, GICHD_TITLE + ', PDF-стр. 839'),
    ('pdf198-5-225c70a5974e', 'ar6', None, GICHD_TITLE + ', PDF-стр. 851'),
    ('pdf198-4-00a79e947c55', 'vur67', None, GICHD_TITLE + ', PDF-стр. 721'),
    ('pdf198-7-76afc4ccf0bf', 'md2', None, GICHD_TITLE + ', PDF-стр. 758'),
    ('pdf198-7-084c0c77412d', 'a20', KOPANINA_URL, 'Копанина.рф — подписанные фотографии А-20; использованы только два правых объекта'),
    ('pdf198-7-884b519e085b', 'k6m', KOPANINA_URL, 'Копанина.рф — подписанный разрез К-6М; использован только внешний контур'),
]


def main():
    WORK.mkdir(parents=True, exist_ok=True)
    data = json.loads(PRODUCTION_CATALOG.read_text(encoding='utf-8'))
    cards = {card['id']: card for card in data['cards']}
    entries = []
    for card_id, name, source_url, source_title in ITEMS:
        card = cards[card_id]
        title = card['title']
        stem = f'reconstruction-v257-{name}'
        if card['images'] and any(image['id'] != stem for image in card['images']):
            raise RuntimeError(f'Refusing to replace existing image: {card_id}')
        card['sources'] = [source for source in card['sources'] if source['id'] != f'source-{stem}']
        with Image.open(AOSEARCH / f'v257_reconstructions/{name}.png') as source:
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
    (WORK / 'reconstruction-batch-v257.json').write_text(json.dumps({
        'batch': 'original-reconstruction-batch-v257',
        'generatedAt': TODAY,
        'entries': entries,
        'build': counts,
    }, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'added': len(entries), 'remainingEmpty': sum(not card['images'] for card in data['cards']), 'build': counts}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
