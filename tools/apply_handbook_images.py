"""Add attributed exterior illustrations without replacing catalog identities."""
import argparse
import json
from pathlib import Path
import sqlite3

from apply_demz_catalog import add_media_and_sources
from apply_uav_reference import normalized

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = ROOT / 'content/overlays/handbook-images-20261019.json'
VERSION = 195


def apply_catalog(path):
    path = Path(path)
    data = json.loads(path.read_text(encoding='utf-8'))
    payload = json.loads(PAYLOAD.read_text(encoding='utf-8'))
    cards = {card['id']: card for card in data['cards']}
    for correction in payload.get('fieldCorrections', []):
        card = cards[correction['cardId']]
        for field in ('body', 'tags'):
            if card[field] not in (correction['before'][field], correction['after'][field]):
                raise ValueError('Unexpected card text: ' + correction['cardId'])
            card[field] = correction['after'][field]
    for change in payload['enrichments']:
        card = cards[change['cardId']]
        for table in ('images', 'sources'):
            known = {row['id']: row for row in card[table]}
            for incoming in change[table]:
                row = dict(incoming)
                if row['id'] in known:
                    existing = known[row['id']]
                    if table == 'images':
                        row['position'] = existing['position']
                    if row != existing:
                        raise ValueError('Existing reference differs: ' + row['id'])
                    continue
                if table == 'images':
                    row['position'] = max((image['position'] for image in card['images']), default=-1) + 1
                card[table].append(row)
                known[row['id']] = row
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def apply_database(path):
    if sqlite3.sqlite_version_info > (3, 45, 1):
        raise RuntimeError('Production database writes require SQLite 3.45.1 or older')
    payload = json.loads(PAYLOAD.read_text(encoding='utf-8'))
    with sqlite3.connect(path) as db:
        db.execute('PRAGMA foreign_keys=ON')
        version = int(db.execute("SELECT value FROM metadata WHERE key='content_version'").fetchone()[0])
        if version not in (188, 194, VERSION):
            raise ValueError('Apply the prepared handbook before its additional images')
        for correction in payload.get('fieldCorrections', []):
            cid = correction['cardId']
            card = db.execute('SELECT title,summary,body,tags FROM cards WHERE id=?', (cid,)).fetchone()
            if card is None:
                raise ValueError('Missing correction target: ' + cid)
            title, summary, body, tags = card
            if (body not in (correction['before']['body'], correction['after']['body']) or
                    tags not in (' · '.join(correction['before']['tags']), ' · '.join(correction['after']['tags']))):
                raise ValueError('Unexpected card text: ' + cid)
            body = correction['after']['body']
            tags = ' · '.join(correction['after']['tags'])
            search = normalized(' '.join([title, summary, body, tags.replace(' · ', ' ')]))
            db.execute('UPDATE cards SET body=?,tags=?,searchText=? WHERE id=?', (body, tags, search, cid))
        for change in payload['enrichments']:
            card = db.execute('SELECT thumbnailPath FROM cards WHERE id=?', (change['cardId'],)).fetchone()
            if card is None:
                raise ValueError('Missing existing card: ' + change['cardId'])
            add_media_and_sources(db, change['cardId'], change['images'], change['sources'])
            if not card[0] and change['images']:
                db.execute('UPDATE cards SET thumbnailPath=? WHERE id=?',
                           (change['images'][0]['thumbnailPath'], change['cardId']))
        target = VERSION if version >= 194 else version
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
        parser.error('Pass --catalog and/or --database')
    if args.catalog:
        apply_catalog(args.catalog)
    if args.database:
        print('Content version:', apply_database(args.database))
