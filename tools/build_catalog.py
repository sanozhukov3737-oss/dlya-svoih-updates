"""Validate developer JSON and build the bundled SQLite asset, using only Python 3.
The output is used by fresh installations and versioned offline update packs. Schema/Room validation is
additionally covered by PackagedDatabaseTest on Android.
"""
import argparse
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile
import unicodedata
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'app/src/main/assets'
PRODUCTION_CATALOG = ROOT / 'content/catalog.json'
PRODUCTION_DATABASE = ASSETS / 'database/guide-v29.db'


def normalize(value):
    return unicodedata.normalize('NFKC', value).lower().replace('ё', 'е')


def unique(rows, key, label):
    values = [row[key] for row in rows]
    if len(values) != len(set(values)):
        raise ValueError(f'Duplicate {label}')


def validate(data):
    if data['formatVersion'] != 1 or not isinstance(data['contentVersion'], int) or data['contentVersion'] < 1:
        raise ValueError('Unsupported content format/version')
    for table in ['countries', 'categories', 'cards']:
        unique(data[table], 'id', table)
    unique(data['cards'], 'rowid', 'card rowid')
    countries = {c['id'] for c in data['countries']}
    if 'ru' not in countries:
        raise ValueError('Russia must remain in country selector')
    categories = {c['id']: c for c in data['categories']}
    image_ids, source_ids = set(), set()
    for card in data['cards']:
        if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,95}', card['id']):
            raise ValueError('Card id must be a stable route-safe id')
        if not isinstance(card['rowid'], int) or card['rowid'] < 1:
            raise ValueError('Invalid rowid')
        if card['section'] not in {'AMMUNITION', 'ATGM', 'SVO', 'MEDICINE'}:
            raise ValueError('Unknown section')
        if categories[card['categoryId']]['section'] != card['section']:
            raise ValueError('Card/category section mismatch')
        for field, limit in [('title', 200), ('summary', 600), ('body', 100_000)]:
            if not isinstance(card[field], str) or not card[field].strip() or len(card[field]) > limit:
                raise ValueError(f'Invalid {field}: {card["id"]}')
        if not isinstance(card.get('modelStatus'), str) or not card['modelStatus'].strip() or len(card['modelStatus']) > 40:
            raise ValueError(f'Invalid model status: {card["id"]}')
        if card.get('sourceGrade') not in {'A', 'B', 'legacy'}:
            raise ValueError(f'Invalid source grade: {card["id"]}')
        if card.get('contentStatus') not in {'demo', 'medical_review_required', 'reviewed', 'source_only', 'candidate'}:
            raise ValueError(f'Invalid content status: {card["id"]}')
        if card.get('verifiedAt') is not None and (not isinstance(card['verifiedAt'], str) or len(card['verifiedAt']) > 40):
            raise ValueError(f'Invalid verification date: {card["id"]}')
        if len(card['countries']) != len(set(card['countries'])) or not set(card['countries']) <= countries:
            raise ValueError('Invalid card country')
        if len(card['images']) > 12:
            raise ValueError('Too many images in a card')
        for picture in card['images']:
            if type(picture.get('position')) is not int or not 0 <= picture['position'] <= 11:
                raise ValueError(f'Invalid image position: {card["id"]}/{picture["id"]}')
            if picture['id'] in image_ids:
                raise ValueError('Duplicate image id')
            image_ids.add(picture['id'])
            for key, folder, limit in [('localPath', 'images', 1600), ('thumbnailPath', 'thumbs', 256)]:
                path = picture[key]
                if not re.fullmatch(folder + r'/[a-zA-Z0-9_-]{1,96}\.(webp|png|jpg|jpeg)', path):
                    raise ValueError('Invalid local image path')
                target = (ASSETS / path).resolve()
                if not target.is_relative_to(ASSETS.resolve()) or not target.is_file() or target.stat().st_size > 4 * 1024 * 1024:
                    raise ValueError('Missing or oversized image')
                with Image.open(target) as image:
                    if not 1 <= image.width <= limit or not 1 <= image.height <= limit or getattr(image, 'n_frames', 1) != 1:
                        raise ValueError('Image dimensions or frame count exceed limits')
                    if key == 'localPath' and (image.width, image.height) != (picture['width'], picture['height']):
                        raise ValueError('Image dimensions do not match metadata')
                    image.verify()
        for source in card['sources']:
            if source['id'] in source_ids:
                raise ValueError('Duplicate source id')
            source_ids.add(source['id'])
            if source['url'] is not None and not source['url'].startswith('https://'):
                raise ValueError('Source URL must use HTTPS')


def build(source, output):
    data = json.loads(Path(source).read_text(encoding='utf-8'))
    validate(data)
    output = Path(output)
    if output.resolve() == PRODUCTION_DATABASE.resolve() and sqlite3.sqlite_version_info > (3, 45, 1):
        raise RuntimeError('Production database generation is pinned to SQLite 3.45.1 or older')
    output.parent.mkdir(parents=True, exist_ok=True)
    # Keep an interrupted production build's scratch files out of Android assets.
    # The staging folder is on the same project filesystem for atomic replace.
    staging = ROOT / 'build/catalog-db' if output.resolve() == PRODUCTION_DATABASE.resolve() else output.parent
    staging.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(dir=staging, suffix='.db')
    os.close(fd)
    db = None
    try:
        db = sqlite3.connect(temp)
        db.executescript((ROOT / 'content/schema.sql').read_text(encoding='utf-8'))
        with db:
            db.executemany('INSERT INTO countries VALUES (:id,:name,:sortOrder)', data['countries'])
            db.executemany('INSERT INTO categories VALUES (:id,:section,:title,:sortOrder)', data['categories'])
            for card in data['cards']:
                fields = {k: card[k] for k in ['rowid','id','section','categoryId','title','summary','body','contentStatus','reviewedAt',
                    'modelStatus','sourceGrade','verifiedAt']}
                fields.update(tags=' · '.join(card['tags']), sortTitle=normalize(card['title']),
                    searchText=normalize(' '.join([card['title'], card['summary'], card['body'], *card['tags']])),
                    thumbnailPath=card['images'][0]['thumbnailPath'] if card['images'] else None)
                db.execute('INSERT INTO cards ('+','.join(fields)+') VALUES ('+','.join(':'+key for key in fields)+')', fields)
                db.executemany('INSERT INTO card_countries VALUES (?,?)', [(card['id'], country) for country in card['countries']])
                db.executemany('INSERT INTO images VALUES (:id,:cardId,:localPath,:caption,:width,:height,:position)',
                    [dict(image, cardId=card['id']) for image in card['images']])
                db.executemany('INSERT INTO sources VALUES (:id,:cardId,:title,:url,:accessedAt)',
                    [dict(source, cardId=card['id']) for source in card['sources']])
            db.execute('INSERT INTO metadata VALUES (?,?)', ('content_version', str(data['contentVersion'])))
        if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok' or db.execute('PRAGMA foreign_key_check').fetchall():
            raise ValueError('Database integrity check failed')
        db.execute("INSERT INTO cards_fts(cards_fts) VALUES ('integrity-check')")
        db.commit()
        db.execute('VACUUM')
        db.close()
        db = None
        os.replace(temp, output)
        (output.parent / "content-version.txt").write_text(str(data["contentVersion"]) + "\n", encoding="ascii")
    finally:
        if db is not None:
            db.close()
        for transient in (Path(temp), Path(temp + '-journal'), Path(temp + '-wal'), Path(temp + '-shm')):
            if transient.exists():
                transient.unlink()
    return {'cards': len(data['cards']), 'countries': len(data['countries']),
        'images': sum(len(c['images']) for c in data['cards']), 'bytes': output.stat().st_size}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, default=PRODUCTION_CATALOG)
    parser.add_argument('--output', type=Path, default=PRODUCTION_DATABASE)
    args = parser.parse_args()
    print(json.dumps(build(args.source, args.output), ensure_ascii=False))
