#!/usr/bin/env python3
"""Recover editable JSON from the verified packaged database without editing it.

The old source is needed only for image-to-thumbnail mappings absent from SQLite.
Every logical content column must survive a build back into a temporary database.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
from build_catalog import ASSETS, PRODUCTION_CATALOG, PRODUCTION_DATABASE, build
from catalog_projection import projections

TABLES = ('countries', 'categories', 'cards', 'card_countries', 'images', 'sources',
          'metadata', 'favorites', 'reading')


def logical_tables(path):
    with sqlite3.connect(f'file:{path}?mode=ro', uri=True) as db:
        assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        assert not db.execute('PRAGMA foreign_key_check').fetchall()
        return {name: sorted(db.execute('SELECT ' + ('rowid,*' if name == 'cards' else '*')
                    + ' FROM "' + name + '"').fetchall(), key=repr) for name in TABLES}


def sync(database, source, report_path):
    original_hash = hashlib.sha256(database.read_bytes()).hexdigest()
    old = json.loads(source.read_text(encoding='utf-8'))
    old_images = {p['id']: p for c in old['cards'] for p in c['images']}
    with sqlite3.connect(f'file:{database}?mode=ro', uri=True) as db:
        db.row_factory = sqlite3.Row
        version = int(db.execute("SELECT value FROM metadata WHERE key='content_version'").fetchone()[0])
        data = dict(formatVersion=1, contentVersion=version, catalogVersion=version,
            countries=[dict(r) for r in db.execute('SELECT * FROM countries ORDER BY sortOrder,id')],
            categories=[dict(r) for r in db.execute('SELECT * FROM categories ORDER BY section,sortOrder,id')], cards=[])
        searches = {}
        for row in db.execute('SELECT rowid,* FROM cards ORDER BY rowid'):
            card = dict(row)
            searches[card['id']] = card.pop('searchText')
            card.pop('sortTitle')  # Recomputed and independently compared during round trip.
            card['tags'] = card['tags'].split(' · ') if card['tags'] else []
            card['countries'] = [r[0] for r in db.execute('SELECT countryId FROM card_countries WHERE cardId=? ORDER BY countryId', (card['id'],))]
            card['images'] = []
            for image in db.execute('SELECT * FROM images WHERE cardId=? ORDER BY position,id', (card['id'],)):
                picture = dict(image); picture.pop('cardId')
                picture['thumbnailPath'] = old_images.get(picture['id'], {}).get('thumbnailPath',
                    'thumbs/' + Path(picture['localPath']).name)
                assert (ASSETS / picture['thumbnailPath']).is_file(), picture['id']
                card['images'].append(picture)
            card['sources'] = [dict(r) for r in db.execute('SELECT id,title,url,accessedAt FROM sources WHERE cardId=? ORDER BY id', (card['id'],))]
            data['cards'].append(card)
    pairs = projections(data['cards'])
    for card in data['cards']:
        pair = pairs[card['id']]
        if searches[card['id']] == pair['reader']:
            card['searchProjection'] = 'reader'
        elif searches[card['id']] == pair['legacy']:
            card['searchProjection'] = 'legacy'
        else:
            raise ValueError('Unrecognized published search projection: ' + card['id'])
    raw = json.dumps(data, ensure_ascii=False, indent=2) + '\n'
    with tempfile.TemporaryDirectory(prefix='catalog-roundtrip-') as directory:
        candidate = Path(directory) / 'catalog.json'; candidate.write_text(raw, encoding='utf-8')
        rebuilt = Path(directory) / 'guide.db'
        counts = build(candidate, rebuilt)
        baseline = logical_tables(database); restored = logical_tables(rebuilt)
        for name in TABLES:
            assert baseline[name] == restored[name], 'Round-trip changed table ' + name
        with sqlite3.connect(rebuilt) as db:
            db.execute("INSERT INTO cards_fts(cards_fts) VALUES ('integrity-check')")
            assert db.execute("SELECT count(*) FROM cards_fts WHERE cards_fts MATCH 'тм'").fetchone()[0] > 0
    assert hashlib.sha256(database.read_bytes()).hexdigest() == original_hash
    source.write_text(raw, encoding='utf-8')
    old_ids = {c['id'] for c in old['cards']}; new_ids = {c['id'] for c in data['cards']}
    report = dict(contentVersion=version, counts=counts, databaseSha256=original_hash,
        sourceSha256=hashlib.sha256(raw.encode()).hexdigest(), sourceBytes=len(raw.encode()),
        databaseUnchanged=True, allLogicalTablesEqual=list(TABLES),
        searchProjections=dict(Counter(c['searchProjection'] for c in data['cards'])),
        restoredMissingIds=sorted(new_ids-old_ids), excludedUnpublishedIds=sorted(old_ids-new_ids),
        integrityCheck='ok', foreignKeyViolations=0, ftsIntegrityCheck='ok')
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if not k.endswith('Ids')}, ensure_ascii=False, indent=2))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, default=PRODUCTION_DATABASE)
    parser.add_argument('--source', type=Path, default=PRODUCTION_CATALOG)
    parser.add_argument('--report', type=Path, default=Path('research/post-0.3.134/catalog-source-sync.json'))
    args = parser.parse_args(); sync(args.database, args.source, args.report)
