#!/usr/bin/env python3
"""Add the owner-approved AR-27 exterior reconstruction (catalog 239)."""
import hashlib
import json
from pathlib import Path
from PIL import Image
from build_catalog import PRODUCTION_CATALOG, PRODUCTION_DATABASE, ASSETS, build

ROOT = Path(__file__).resolve().parents[1]
AOSEARCH = ROOT.parent / 'aosearch'
VERSION = 239
TODAY = '2026-11-02'
BANK = AOSEARCH / 'v239_reconstructions'
WORK = ROOT / 'build/catalog239-reconstruction-batch'
ITEMS = json.loads((AOSEARCH / 'v239_items.json').read_text(encoding='utf-8'))
SOURCE_TITLE = 'Руководство службы. Радиовзрыватель АР-27, 1974'
SOURCE_URL = 'https://ukr.bulletpicker.com/pdf/%D0%A0%D1%83%D0%BA%D0%BE%D0%B2%D0%BE%D0%B4%D1%81%D1%82%D0%B2%D0%BE%20%D1%81%D0%BB%D1%83%D0%B6%D0%B1%D1%8B%20%D0%A0%D0%B0%D0%B4%D0%B8%D0%BE%D0%B2%D0%B7%D1%80%D1%8B%D0%B2%D0%B0%D1%82%D0%B5%D0%BB%D1%8C%20%D0%90%D0%A0-27%20%281974%29.pdf'


def main():
    WORK.mkdir(parents=True, exist_ok=True)
    data = json.loads(PRODUCTION_CATALOG.read_text(encoding='utf-8'))
    cards = {c['id']: c for c in data['cards']}
    entries = []
    for item in [x for x in ITEMS if x['stem'] == 'ar27']:
        slug = item['stem']
        card = cards[item['cardId']]
        title = item['title']
        stem = f'reconstruction-v239-{slug}'
        if card['images'] and any(image['id'] != stem for image in card['images']):
            raise RuntimeError(f'Unexpected existing image: {item["cardId"]}')
        raster = Image.open(BANK / 'ar27_corrected.png').convert('RGB')
        raster.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
        full_rel = f'images/{stem}.webp'
        thumb_rel = f'thumbs/{stem}.webp'
        full = ASSETS / full_rel
        thumb = ASSETS / thumb_rel
        raster.save(full, 'WEBP', quality=90, method=6)
        miniature = raster.copy()
        miniature.thumbnail((256, 256), Image.Resampling.LANCZOS)
        miniature.save(thumb, 'WEBP', quality=84, method=6)
        locator = ', PDF-страница 6'
        card['images'] = [{
            'id': stem,
            'localPath': full_rel,
            'caption': f'{title} — иллюстративная реконструкция внешнего вида по открытому источнику{locator}. Не фотография и не рабочий чертёж; маркировка и клейма не воспроизводятся.',
            'width': raster.width,
            'height': raster.height,
            'position': 0,
            'thumbnailPath': thumb_rel,
        }]
        card['thumbnailPath'] = thumb_rel
        card['sources'] = [source for source in card['sources'] if source['id'] != f'source-{stem}']
        card['sources'].append({
            'id': f'source-{stem}',
            'title': f'{title} — {SOURCE_TITLE}{locator}; исходная иллюстрация в каталог не копировалась',
            'url': SOURCE_URL,
            'accessedAt': TODAY,
        })
        entries.append({
            'cardId': item['cardId'],
            'imageId': stem,
            'fullSha256': hashlib.sha256(full.read_bytes()).hexdigest(),
            'thumbnailSha256': hashlib.sha256(thumb.read_bytes()).hexdigest(),
            'license': 'Original AI-assisted illustrative reconstruction; no source image redistributed',
            'sourceReference': SOURCE_URL,
            'sourcePage': 6,
            'status': 'Approved by owner',
        })
    if len(entries) != 1:
        raise RuntimeError(f'Expected 1, got {len(entries)}')
    data['contentVersion'] = data['catalogVersion'] = VERSION
    PRODUCTION_CATALOG.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (ASSETS / 'database/content-version.txt').write_text(f'{VERSION}\n')
    counts = build(PRODUCTION_CATALOG, PRODUCTION_DATABASE)
    (WORK / 'reconstruction-batch-v239.json').write_text(json.dumps({
        'batch': 'original-reconstruction-batch-v239',
        'generatedAt': TODAY,
        'entries': entries,
        'build': counts,
    }, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'added': len(entries), 'build': counts}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
