"""Add the page-by-page DEMZ catalog references to the preserved catalog."""
import argparse
import json
from pathlib import Path
import sqlite3
from apply_uav_reference import normalized

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = ROOT / 'content/overlays/demz-catalog-20261019.json'
VERSION = 193


def apply_catalog(path):
    path = Path(path)
    data = json.loads(path.read_text(encoding='utf-8'))
    payload = json.loads(PAYLOAD.read_text(encoding='utf-8'))
    for table in ('categories', 'cards'):
        existing = {r['id']: r for r in data[table]}
        for row in payload[table]:
            if row['id'] in existing:
                if existing[row['id']] != row:
                    raise ValueError('Existing record differs: ' + row['id'])
            else:
                if table == 'cards' and any(c['rowid'] == row['rowid'] for c in data['cards']):
                    raise ValueError('Card rowid collision')
                data[table].append(row)
    cards = {c['id']: c for c in data['cards']}
    for change in payload['enrichments']:
        card = cards[change['cardId']]
        if change['addCountry'] and change['addCountry'] not in card['countries']:
            card['countries'].append(change['addCountry'])
        if change['bodyAppend'] and change['bodyAppend'] not in card['body']:
            card['body'] += change['bodyAppend']
        for table in ('sources', 'images'):
            known = {r['id'] for r in card[table]}
            for row in change[table]:
                if row['id'] in known:
                    continue
                row = dict(row)
                if table == 'images':
                    row['position'] = max((r['position'] for r in card['images']), default=-1) + 1
                card[table].append(row)
    # The developer source remains on its historical baseline. The full
    # published 190 catalog is restored before both overlays are applied in CI.
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def add_media_and_sources(db, card_id, images, sources):
    for image in images:
        existing = db.execute('SELECT cardId,localPath,caption,width,height FROM images WHERE id=?', (image['id'],)).fetchone()
        fields = (card_id, image['localPath'], image['caption'], image['width'], image['height'])
        if existing is not None:
            if existing != fields:
                raise ValueError('Image collision: ' + image['id'])
            continue
        position = db.execute('SELECT COALESCE(MAX(position),-1)+1 FROM images WHERE cardId=?', (card_id,)).fetchone()[0]
        db.execute('INSERT INTO images VALUES (?,?,?,?,?,?,?)', (image['id'], *fields, position))
    for source in sources:
        fields = (source['id'], card_id, source['title'], source['url'], source['accessedAt'])
        existing = db.execute('SELECT * FROM sources WHERE id=?', (source['id'],)).fetchone()
        if existing is not None and existing != fields:
            raise ValueError('Source collision: ' + source['id'])
        db.execute('INSERT OR IGNORE INTO sources VALUES (?,?,?,?,?)', fields)


def apply_database(path):
    if sqlite3.sqlite_version_info > (3, 45, 1):
        raise RuntimeError('Production database writes require SQLite 3.45.1 or older')
    payload = json.loads(PAYLOAD.read_text(encoding='utf-8'))
    with sqlite3.connect(path) as db:
        db.execute('PRAGMA foreign_keys=ON')
        version = int(db.execute("SELECT value FROM metadata WHERE key='content_version'").fetchone()[0])
        if version not in (188, 192, VERSION):
            raise ValueError('Apply the prepared UAV references before the full DEMZ overlay')
        for row in payload['categories']:
            fields = (row['id'], row['section'], row['title'], row['sortOrder'])
            existing = db.execute('SELECT * FROM categories WHERE id=?', (row['id'],)).fetchone()
            if existing is not None and existing != fields:
                raise ValueError('Category collision')
            db.execute('INSERT OR IGNORE INTO categories VALUES (?,?,?,?)', fields)
        for card in payload['cards']:
            fields = {k: card[k] for k in ('rowid','id','section','categoryId','title','summary','body',
                      'contentStatus','reviewedAt','modelStatus','sourceGrade','verifiedAt')}
            fields.update(tags=' · '.join(card['tags']), sortTitle=normalized(card['title']),
                          searchText=normalized(' '.join([card['title'],card['summary'],card['body'],*card['tags']])),
                          thumbnailPath=card['images'][0]['thumbnailPath'])
            columns = ','.join(fields)
            existing = db.execute('SELECT ' + columns + ' FROM cards WHERE id=?', (card['id'],)).fetchone()
            if existing is not None and existing != tuple(fields.values()):
                raise ValueError('Card collision: ' + card['id'])
            if existing is None:
                db.execute('INSERT INTO cards (' + columns + ') VALUES (' + ','.join('?' for _ in fields) + ')', tuple(fields.values()))
            db.executemany('INSERT OR IGNORE INTO card_countries VALUES (?,?)', [(card['id'],c) for c in card['countries']])
            add_media_and_sources(db, card['id'], card['images'], card['sources'])
        for change in payload['enrichments']:
            card = db.execute('SELECT title,summary,body,tags FROM cards WHERE id=?', (change['cardId'],)).fetchone()
            if card is None:
                raise ValueError('Missing existing card: ' + change['cardId'])
            title, summary, body, tags = card
            if change['bodyAppend'] and change['bodyAppend'] not in body:
                body += change['bodyAppend']
                search = normalized(' '.join([title,summary,body.split('\n\n## Служебные сведения',1)[0],tags.replace(' · ', ' ')]))
                db.execute('UPDATE cards SET body=?,searchText=? WHERE id=?', (body,search,change['cardId']))
            if change['addCountry']:
                db.execute('INSERT OR IGNORE INTO card_countries VALUES (?,?)', (change['cardId'],change['addCountry']))
            add_media_and_sources(db, change['cardId'], change['images'], change['sources'])
        target = VERSION if version >= 192 else version
        db.execute("UPDATE metadata SET value=? WHERE key='content_version'", (str(target),))
        if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok' or db.execute('PRAGMA foreign_key_check').fetchall():
            raise ValueError('Database integrity failed')
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
