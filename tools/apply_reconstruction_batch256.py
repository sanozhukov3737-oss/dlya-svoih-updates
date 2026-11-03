#!/usr/bin/env python3
"""Add six owner-approved exterior reconstructions to previously empty cards (catalog 256)."""
import hashlib
import json
from pathlib import Path
from PIL import Image
from build_catalog import PRODUCTION_CATALOG, PRODUCTION_DATABASE, ASSETS, build

ROOT = Path(__file__).resolve().parents[1]
AOSEARCH = ROOT.parent / 'aosearch'
VERSION = 256
TODAY = '2026-11-03'
WORK = ROOT / 'build/catalog256-reconstruction-batch'
GICHD_TITLE = 'GICHD — Explosive Ordnance Guide for Ukraine, четвёртая редакция, локальная проверенная копия'
KOPANINA_URL = None
ITEMS = [
    ('pdf198-4-dbff41ab0687', 'vzd1m', None, GICHD_TITLE + ', PDF-стр. 777'),
    ('pdf198-7-feb3c0b72679', 'k6', KOPANINA_URL, 'Копанина.рф — подписанная фотография К-6 рядом с А-20'),
    ('pdf198-5-10e41fa1c0ad', 'vp9', None, GICHD_TITLE + ', PDF-стр. 809–810'),
    ('pdf198-7-ec30824558ff', 'md5', None, GICHD_TITLE + ', PDF-стр. 728'),
    ('pdf198-7-73185defb349', 'mg201', KOPANINA_URL, 'Копанина.рф — подписанный разрез МГ-201; использован только внешний контур'),
    ('pdf198-7-22adaec49baa', 'mg202', KOPANINA_URL, 'Копанина.рф — подписанный разрез МГ-202; использован только внешний контур'),
]


def main():
    WORK.mkdir(parents=True, exist_ok=True)
    data = json.loads(PRODUCTION_CATALOG.read_text(encoding='utf-8'))
    cards = {card['id']: card for card in data['cards']}
    assert next(c for c in data['cards'] if c['id'] == 'ordnance-v27-m-6-vzryvatel')['images'], 'M-6 must retain existing images'
    entries = []
    for card_id, name, source_url, source_title in ITEMS:
        card = cards[card_id]
        title = card['title']
        stem = f'reconstruction-v256-{name}'
        if card['images'] and any(image['id'] != stem for image in card['images']):
            raise RuntimeError(f'Refusing to replace existing image: {card_id}')
        card['sources'] = [source for source in card['sources'] if source['id'] != f'source-{stem}']
        raster = Image.open(AOSEARCH / f'v256_reconstructions/{name}.png').convert('RGB')
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
    (WORK / 'reconstruction-batch-v256.json').write_text(json.dumps({
        'batch': 'original-reconstruction-batch-v256',
        'generatedAt': TODAY,
        'entries': entries,
        'skipped': [{'cardId': 'ordnance-v27-m-6-vzryvatel', 'reason': 'Existing two images preserved'}],
        'build': counts,
    }, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'added': len(entries), 'remainingEmpty': sum(not card['images'] for card in data['cards']), 'build': counts}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
