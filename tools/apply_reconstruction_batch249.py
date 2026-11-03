#!/usr/bin/env python3
"""Add the owner-approved PD10KA exterior reconstruction (catalog 249)."""
import hashlib
import json
from pathlib import Path
from PIL import Image
from build_catalog import PRODUCTION_CATALOG, PRODUCTION_DATABASE, ASSETS, build

ROOT = Path(__file__).resolve().parents[1]
AOSEARCH = ROOT.parent / 'aosearch'
VERSION = 249
TODAY = '2026-11-03'
WORK = ROOT / 'build/catalog249-reconstruction-batch'
CARD_ID = 'pdf198-8-43c3ddedc56c'
SOURCE_URL = 'https://product.itdrone.com.ua/pd10/pd10ka58'
SOURCE_TITLE = 'официальная страница производителя IT Drone, отдельная фотография PD10KA'


def main():
    WORK.mkdir(parents=True, exist_ok=True)
    data = json.loads(PRODUCTION_CATALOG.read_text(encoding='utf-8'))
    card = next(c for c in data['cards'] if c['id'] == CARD_ID)
    title = card['title']
    stem = 'reconstruction-v249-pd10ka'
    if card['images'] and any(image['id'] != stem for image in card['images']):
        raise RuntimeError(f'Unexpected existing image: {CARD_ID}')
    raster = Image.open(AOSEARCH / 'v249_reconstructions/pd10ka.png').convert('RGB')
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
        'caption': f'{title} — иллюстративная реконструкция только внешнего вида по официальной фотографии производителя. Не фотография и не рабочий чертёж; полезная нагрузка, маркировка, надписи и логотипы не воспроизводятся.',
        'width': raster.width,
        'height': raster.height,
        'position': 0,
        'thumbnailPath': thumb_rel,
    }]
    card['thumbnailPath'] = thumb_rel
    card['sources'] = [source for source in card['sources'] if source['id'] != f'source-{stem}']
    card['sources'].append({
        'id': f'source-{stem}',
        'title': f'{title} — {SOURCE_TITLE}; исходная фотография в каталог не копировалась',
        'url': SOURCE_URL,
        'accessedAt': TODAY,
    })
    entry = {
        'cardId': CARD_ID,
        'imageId': stem,
        'fullSha256': hashlib.sha256(full.read_bytes()).hexdigest(),
        'thumbnailSha256': hashlib.sha256(thumb.read_bytes()).hexdigest(),
        'license': 'AI-assisted original illustrative exterior reconstruction based on a manufacturer reference',
        'sourceReference': SOURCE_URL,
        'sourcePage': 0,
        'status': 'Approved by owner',
    }
    data['contentVersion'] = data['catalogVersion'] = VERSION
    PRODUCTION_CATALOG.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (ASSETS / 'database/content-version.txt').write_text(f'{VERSION}\n', encoding='utf-8')
    counts = build(PRODUCTION_CATALOG, PRODUCTION_DATABASE)
    (WORK / 'reconstruction-batch-v249.json').write_text(json.dumps({
        'batch': 'original-reconstruction-batch-v249',
        'generatedAt': TODAY,
        'entries': [entry],
        'build': counts,
    }, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'added': 1, 'build': counts}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
