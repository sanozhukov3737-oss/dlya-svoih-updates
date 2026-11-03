#!/usr/bin/env python3
"""Add the owner-approved batch of ten exterior reconstructions (catalog 255)."""
import hashlib
import json
from pathlib import Path
from PIL import Image
from build_catalog import PRODUCTION_CATALOG, PRODUCTION_DATABASE, ASSETS, build

ROOT = Path(__file__).resolve().parents[1]
AOSEARCH = ROOT.parent / 'aosearch'
VERSION = 255
TODAY = '2026-11-03'
WORK = ROOT / 'build/catalog255-reconstruction-batch'
ITEMS = [
    ('pdf198-7-453ba1f1652b', 'rpg41', 'https://blokadamus.ru/2024/08/12/ленинградку-ворошиловский-килог/', 'музейная экспозиция, фотография Павла Даиси / MR7; на витрине указан общий образец РПГ-41 «ВК»'),
    ('pdf198-7-e06f74d0ccf5', 'rpg41vk', 'https://blokadamus.ru/2024/08/12/ленинградку-ворошиловский-килог/', 'музейная экспозиция, фотография Павла Даиси / MR7; на витрине указан общий образец РПГ-41 «ВК»'),
    ('pdf198-7-f9079e07f315', 'rpg43', 'https://ordnance.info/?product=rpg-43', 'открытая энциклопедия Ordnance.info, отдельная музейная фотография РОГ-43'),
    ('pdf198-7-24c64848b7ea', 'vpgs41', 'https://www.imfdb.org/wiki/VPGS-41', 'открытая справочная статья IMFDB о ВПГС-41'),
    ('pdf198-7-a00681a8193d', 'sc10', 'https://www.lexpev.nl/fuzesandigniters/germany/sc10dw.html', 'открытый справочник Lexpev, иллюстрация SC 10 DW'),
    ('ref-v10-imp', 'imp', 'https://commons.wikimedia.org/wiki/File:IMP_AP-mine.JPEG', 'Wikimedia Commons, фотография PFC Tracey L. Hall-Leahy, PD-USGov-Military'),
    ('pdf198-7-9911171f2bec', 'muv1940', 'https://biblio-klad.ru/dir/skhemy_vopov/detonatory_vzryvateli/159', 'открытая справочная иллюстрация МУВ обр. 1940 г.'),
    ('pdf198-7-736c23fbc37c', 'muv1942', 'https://biblio-klad.ru/dir/skhemy_vopov/detonatory_vzryvateli/159', 'открытая справочная иллюстрация МУВ обр. 1942 г.'),
    ('pdf198-7-52ac585a62f1', 'charushin', 'https://weaponland.ru/photo/zapal_charushina/8-0-154', 'открытая справочная иллюстрация запала Чарушина'),
    ('pdf198-7-ce6c7c19e7fe', 'zz31', 'https://weaponland.ru/photo/zugzunder_31/8-0-108', 'открытая справочная иллюстрация Z.Z.31'),
]


def main():
    WORK.mkdir(parents=True, exist_ok=True)
    data = json.loads(PRODUCTION_CATALOG.read_text(encoding='utf-8'))
    cards = {card['id']: card for card in data['cards']}
    entries = []
    for card_id, name, source_url, source_title in ITEMS:
        card = cards[card_id]
        title = card['title']
        stem = f'reconstruction-v255-{name}'
        if card['images'] and any(image['id'] != stem for image in card['images']):
            raise RuntimeError(f'Unexpected existing image: {card_id}')
        raster = Image.open(AOSEARCH / f'v255_reconstructions/{name}.png').convert('RGB')
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
        card['sources'] = [source for source in card['sources'] if source['id'] != f'source-{stem}']
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
    (WORK / 'reconstruction-batch-v255.json').write_text(json.dumps({
        'batch': 'original-reconstruction-batch-v255',
        'generatedAt': TODAY,
        'entries': entries,
        'build': counts,
    }, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'added': len(entries), 'remainingEmpty': sum(not card['images'] for card in data['cards']), 'build': counts}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
