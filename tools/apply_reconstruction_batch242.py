#!/usr/bin/env python3
"""Add the owner-approved RPG-28 exterior reconstruction (catalog 242)."""
import hashlib
import json
from pathlib import Path
from PIL import Image
from build_catalog import PRODUCTION_CATALOG, PRODUCTION_DATABASE, ASSETS, build

ROOT = Path(__file__).resolve().parents[1]
AOSEARCH = ROOT.parent / 'aosearch'
VERSION = 242
TODAY = '2026-11-02'
WORK = ROOT / 'build/catalog242-reconstruction-batch'
CARD_ID = 'pdf198-2-5079a982055e'
SOURCE_URL = 'https://commons.wikimedia.org/wiki/File:RPG-28_grenade_launcher_at_Interpolitex-2016_01.jpg'
SOURCE_TITLE = 'RPG-28 at Interpolitex-2016, фотография Vitaly V. Kuzmin, CC BY-SA 4.0'


def main():
    WORK.mkdir(parents=True, exist_ok=True)
    data = json.loads(PRODUCTION_CATALOG.read_text(encoding='utf-8'))
    card = next(c for c in data['cards'] if c['id'] == CARD_ID)
    title = card['title']
    stem = 'reconstruction-v242-rpg28'
    if card['images'] and any(image['id'] != stem for image in card['images']):
        raise RuntimeError(f'Unexpected existing image: {CARD_ID}')
    raster = Image.open(AOSEARCH / 'v242_reconstructions/rpg28.png').convert('RGB')
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
        'caption': f'{title} — иллюстративная реконструкция внешнего вида по открытой музейной фотографии. Не фотография и не рабочий чертёж; маркировка, надписи и учебные вырезы не воспроизводятся.',
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
        'license': 'AI-assisted illustrative reconstruction based on CC BY-SA 4.0 reference; CC BY-SA 4.0',
        'sourceReference': SOURCE_URL,
        'sourcePage': 0,
        'status': 'Approved by owner',
    }
    data['contentVersion'] = data['catalogVersion'] = VERSION
    PRODUCTION_CATALOG.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (ASSETS / 'database/content-version.txt').write_text(f'{VERSION}\n', encoding='utf-8')
    counts = build(PRODUCTION_CATALOG, PRODUCTION_DATABASE)
    (WORK / 'reconstruction-batch-v242.json').write_text(json.dumps({
        'batch': 'original-reconstruction-batch-v242',
        'generatedAt': TODAY,
        'entries': [entry],
        'build': counts,
    }, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'added': 1, 'build': counts}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
