#!/usr/bin/env python3
"""Add the owner-approved Model 1948 exterior reconstruction (catalog 260)."""
import hashlib
import json
from pathlib import Path
from PIL import Image
from build_catalog import PRODUCTION_CATALOG, PRODUCTION_DATABASE, ASSETS, build

ROOT = Path(__file__).resolve().parents[1]
AOSEARCH = ROOT.parent / 'aosearch'
VERSION = 260
TODAY = '2026-11-03'
WORK = ROOT / 'build/catalog260-reconstruction-batch'
SOURCE_URL = 'https://bulletpicker.com/landmine_-apers_-model-1948.html'
SOURCE_TITLE = 'TM 5-280, Foreign Mine Warfare Equipment, PDF-стр. 249, рис. 9-29'
ITEMS = [
    ('ordnance-v27-model-1948-ap-mine-vetnam', 'model1948', SOURCE_TITLE),
]


def main():
    WORK.mkdir(parents=True, exist_ok=True)
    data = json.loads(PRODUCTION_CATALOG.read_text(encoding='utf-8'))
    cards = {card['id']: card for card in data['cards']}
    entries = []
    for card_id, name, source_title in ITEMS:
        if card_id not in cards:
            raise RuntimeError(f'Missing card {card_id!r}; catalog={PRODUCTION_CATALOG}; matches={[key for key in cards if "1948" in key]!r}')
        card = cards[card_id]
        title = card['title']
        stem = f'reconstruction-v260-{name}'
        if card['images'] and any(image['id'] != stem for image in card['images']):
            raise RuntimeError(f'Refusing to replace existing image: {card_id}')
        card['sources'] = [source for source in card['sources'] if source['id'] != f'source-{stem}']
        with Image.open(AOSEARCH / f'v260_reconstructions/{name}.png') as source:
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
            'title': f'{title} — {source_title}; модель указана в пособии как французская; исходное изображение в каталог не копировалось',
            'url': SOURCE_URL,
            'accessedAt': TODAY,
        })
        entries.append({
            'cardId': card_id,
            'imageId': stem,
            'fullSha256': hashlib.sha256(full.read_bytes()).hexdigest(),
            'thumbnailSha256': hashlib.sha256(thumb.read_bytes()).hexdigest(),
            'license': 'AI-assisted original illustrative exterior reconstruction based on open references',
            'sourceReference': SOURCE_URL,
            'sourcePage': 249,
            'status': 'Approved by owner',
        })
    data['contentVersion'] = data['catalogVersion'] = VERSION
    PRODUCTION_CATALOG.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (ASSETS / 'database/content-version.txt').write_text(f'{VERSION}\n', encoding='utf-8')
    counts = build(PRODUCTION_CATALOG, PRODUCTION_DATABASE)
    (WORK / 'reconstruction-batch-v260.json').write_text(json.dumps({
        'batch': 'original-reconstruction-batch-v260',
        'generatedAt': TODAY,
        'entries': entries,
        'build': counts,
    }, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'added': len(entries), 'remainingEmpty': sum(not card['images'] for card in data['cards']), 'build': counts}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
