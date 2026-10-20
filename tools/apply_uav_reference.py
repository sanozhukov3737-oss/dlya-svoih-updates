"""Add the curated UAV reference cards after restoring the published catalog.

The overlay contains exterior views and descriptive identification information.
It does not assign compatibility with individual aircraft models.
"""
import argparse
import json
from pathlib import Path
import sqlite3
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = ROOT / 'content/overlays/uav-reference-20261019.json'
VERSION = 192


def normalized(value):
    return unicodedata.normalize('NFKC', value).lower().replace('ё', 'е')


def apply_catalog(path):
    path = Path(path)
    data = json.loads(path.read_text(encoding='utf-8'))
    payload = json.loads(PAYLOAD.read_text(encoding='utf-8'))
    for table in ('categories', 'cards'):
        existing = {r['id']: r for r in data[table]}
        for row in payload[table]:
            if row['id'] in existing:
                if existing[row['id']] != row:
                    raise ValueError('Existing catalog record differs: ' + row['id'])
            else:
                if table == 'cards' and any(r['rowid'] == row['rowid'] for r in data[table]):
                    raise ValueError('Card rowid collision')
                data[table].append(row)
    # The legacy developer JSON remains version 188; the immutable published
    # catalog is restored and brought forward to 192 independently before CI.
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def apply_database(path):
    if sqlite3.sqlite_version_info > (3, 45, 1):
        raise RuntimeError('Production database writes require SQLite 3.45.1 or older')
    payload = json.loads(PAYLOAD.read_text(encoding='utf-8'))
    with sqlite3.connect(path) as db:
        db.execute('PRAGMA foreign_keys=ON')
        version = int(db.execute("SELECT value FROM metadata WHERE key='content_version'").fetchone()[0])
        if version not in (188, 191, VERSION):
            raise ValueError('Apply the UPM-O correction before adding UAV references')
        for row in payload['categories']:
            values = (row['id'], row['section'], row['title'], row['sortOrder'])
            existing = db.execute('SELECT id,section,title,sortOrder FROM categories WHERE id=?', (row['id'],)).fetchone()
            if existing is not None and existing != values:
                raise ValueError('Existing category differs: ' + row['id'])
            db.execute('INSERT OR IGNORE INTO categories VALUES (?,?,?,?)', values)
        for card in payload['cards']:
            fields = {k: card[k] for k in ('rowid', 'id', 'section', 'categoryId', 'title', 'summary',
                      'body', 'contentStatus', 'reviewedAt', 'modelStatus', 'sourceGrade', 'verifiedAt')}
            fields.update(tags=' · '.join(card['tags']), sortTitle=normalized(card['title']),
                          searchText=normalized(' '.join([card['title'], card['summary'], card['body'], *card['tags']])),
                          thumbnailPath=card['images'][0]['thumbnailPath'] if card['images'] else None)
            columns = ','.join(fields)
            existing = db.execute('SELECT ' + columns + ' FROM cards WHERE id=?', (card['id'],)).fetchone()
            if existing is not None:
                if existing != tuple(fields.values()):
                    raise ValueError('Existing card differs: ' + card['id'])
                continue
            db.execute('INSERT INTO cards (' + columns + ') VALUES (' + ','.join('?' for _ in fields) + ')',
                       tuple(fields.values()))
            db.executemany('INSERT INTO card_countries VALUES (?,?)', [(card['id'], c) for c in card['countries']])
            db.executemany('INSERT INTO images VALUES (:id,:cardId,:localPath,:caption,:width,:height,:position)',
                           [dict(image, cardId=card['id']) for image in card['images']])
            db.executemany('INSERT INTO sources VALUES (:id,:cardId,:title,:url,:accessedAt)',
                           [dict(source, cardId=card['id']) for source in card['sources']])
        target = VERSION if version >= 191 else version
        db.execute("UPDATE metadata SET value=? WHERE key='content_version'", (str(target),))
        if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok' or db.execute('PRAGMA foreign_key_check').fetchall():
            raise ValueError('Catalog integrity check failed')
        db.execute("INSERT INTO cards_fts(cards_fts) VALUES ('integrity-check')")
    return target


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--catalog', type=Path)
    parser.add_argument('--database', type=Path)
    args = parser.parse_args()
    if not args.catalog and not args.database:
        parser.error('Provide --catalog and/or --database')
    if args.catalog:
        apply_catalog(args.catalog)
    if args.database:
        print(apply_database(args.database))
