"""Append identification references from the supplied 26-page handbook."""
import argparse
import json
from pathlib import Path
import sqlite3

from apply_demz_catalog import add_media_and_sources
from apply_uav_reference import normalized

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = ROOT / 'content/overlays/uav-handbook-20261019.json'
VERSION = 194


def apply_catalog(path):
    path = Path(path)
    data = json.loads(path.read_text(encoding='utf-8'))
    payload = json.loads(PAYLOAD.read_text(encoding='utf-8'))
    cards = {card['id']: card for card in data['cards']}
    rowids = {card['rowid'] for card in data['cards']}
    for card in payload['cards']:
        existing = cards.get(card['id'])
        if existing is not None:
            if existing != card:
                raise ValueError('Existing card differs: ' + card['id'])
            continue
        if card['rowid'] in rowids:
            raise ValueError('Card rowid collision')
        data['cards'].append(card)
        cards[card['id']] = card
        rowids.add(card['rowid'])
    for change in payload['enrichments']:
        card = cards[change['cardId']]
        sources = {source['id']: source for source in card['sources']}
        for source in change['sources']:
            if source['id'] in sources:
                if sources[source['id']] != source:
                    raise ValueError('Source collision: ' + source['id'])
            else:
                card['sources'].append(source)
    # Preserve the historical source baseline. CI restores published catalog 190
    # and applies every prepared overlay before advancing the packaged version.
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def apply_database(path):
    if sqlite3.sqlite_version_info > (3, 45, 1):
        raise RuntimeError('Production database writes require SQLite 3.45.1 or older')
    payload = json.loads(PAYLOAD.read_text(encoding='utf-8'))
    with sqlite3.connect(path) as db:
        db.execute('PRAGMA foreign_keys=ON')
        version = int(db.execute("SELECT value FROM metadata WHERE key='content_version'").fetchone()[0])
        if version not in (188, 193, VERSION):
            raise ValueError('Apply the prepared DEMZ catalog before the UAV handbook')
        for card in payload['cards']:
            fields = {key: card[key] for key in (
                'rowid', 'id', 'section', 'categoryId', 'title', 'summary', 'body',
                'contentStatus', 'reviewedAt', 'modelStatus', 'sourceGrade', 'verifiedAt')}
            fields.update(
                tags=' · '.join(card['tags']),
                sortTitle=normalized(card['title']),
                searchText=normalized(' '.join([
                    card['title'], card['summary'], card['body'], *card['tags']])),
                thumbnailPath=card['images'][0]['thumbnailPath'] if card['images'] else None)
            columns = ','.join(fields)
            existing = db.execute('SELECT ' + columns + ' FROM cards WHERE id=?', (card['id'],)).fetchone()
            if existing is not None and existing != tuple(fields.values()):
                raise ValueError('Card collision: ' + card['id'])
            if existing is None:
                db.execute('INSERT INTO cards (' + columns + ') VALUES (' +
                           ','.join('?' for _ in fields) + ')', tuple(fields.values()))
            db.executemany('INSERT OR IGNORE INTO card_countries VALUES (?,?)',
                           [(card['id'], country) for country in card['countries']])
            add_media_and_sources(db, card['id'], card['images'], card['sources'])
        for change in payload['enrichments']:
            if db.execute('SELECT 1 FROM cards WHERE id=?', (change['cardId'],)).fetchone() is None:
                raise ValueError('Missing existing card: ' + change['cardId'])
            add_media_and_sources(db, change['cardId'], [], change['sources'])
        target = VERSION if version >= 193 else version
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
