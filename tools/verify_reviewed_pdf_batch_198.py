"""Verify a SHA-pinned exterior-image batch against JSON, assets and native SQLite."""
from pathlib import Path
import argparse
import copy
import hashlib
import json
import re
import sqlite3
from PIL import Image
from build_catalog import validate

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'app/src/main/assets'


def verify(baseline, catalog, database, overlay):
    raw = Path(baseline).read_bytes()
    before = json.loads(raw)
    after = json.loads(Path(catalog).read_text())
    batch = json.loads(Path(overlay).read_text())
    assert hashlib.sha256(raw).hexdigest() == batch['baseCatalogSha256']
    validate(after)
    old = {c['id']: c for c in before['cards']}
    final = {c['id']: c for c in after['cards']}
    changes = {c['cardId']: c for c in batch['changes']}
    additions = {c['id']: c for c in batch['cards']}
    assert set(final) == set(old) | set(additions)
    assert not set(old) & set(additions)
    assert len({c['rowid'] for c in final.values()}) == len(final)
    for cid, card in old.items():
        expected = copy.deepcopy(card)
        if cid in changes:
            ch = changes[cid]
            assert set(ch['after']) <= {'images', 'sources', 'thumbnailPath'}
            assert ch['before'] == {k: card.get(k) for k in ch['before']}
            expected.update(ch['after'])
            previous_images = {i['id'] for i in card['images']}
            assert previous_images <= {i['id'] for i in expected['images']}
            assert card['sources'] == expected['sources'][:len(card['sources'])]
        assert final[cid] == expected, cid
    for cid, card in additions.items():
        assert final[cid] == card
        assert card['contentStatus'] == 'source_only' and card['sourceGrade'] == 'B'
        assert card['verifiedAt'] is None and card['reviewedAt'] is None
        assert len(card['sources']) >= 1

    for c in final.values():
        assert sorted(i['position'] for i in c['images']) == list(range(len(c['images'])))

    manifest = json.loads((Path(overlay).parents[2] / 'research' / Path(overlay).stem / 'assets-manifest.json').read_text())
    files = {r['path']: r for r in manifest['files']}
    for name, entry in files.items():
        data = (ASSETS / name).read_bytes()
        assert len(data) == entry['bytes'] and hashlib.sha256(data).hexdigest() == entry['sha256']
        with Image.open(ASSETS / name) as image:
            image.load()
    replacements = 0
    for r in batch['review']:
        image = r['asset']
        assert all(image[k] in files for k in ('localPath', 'thumbnailPath'))
        assert image['width'] <= r['nativeSize'][0] and image['height'] <= r['nativeSize'][1]
        if r.get('cropBox'):
            x0, y0, x1, y1 = r['cropBox']
            assert (image['width'], image['height']) == (x1-x0, y1-y0)
            assert 0 <= x0 < x1 <= r['nativeSize'][0] and 0 <= y0 < y1 <= r['nativeSize'][1]
        if r['decision'] == 'replace':
            replacements += 1
            previous = next(i for i in old[r['cardId']]['images'] if i['id'] == image['id'])
            if 'school-images-b5' in str(overlay):
                assert image['width']*image['height'] > previous['width']*previous['height']*1.3
            if r.get('replacementPosition', 0):
                assert final[r['cardId']]['images'][0] == old[r['cardId']]['images'][0]
                assert final[r['cardId']]['thumbnailPath'] == old[r['cardId']]['thumbnailPath']

    special = {}
    if 'school-images-b4' in str(overlay):
        assert len(additions) == 48 and len(batch['review']) == 81
        for cid in ('pdf198-school4-mi-apid-51-trap', 'pdf198-school4-mi-ap-id-51',
                    'pdf198-school4-pmr3-new-yu', 'pdf198-school4-hl-sp-mi-4672'):
            assert cid in additions
        assert not any('ts-2-4' in cid or 'stockmine' in cid for cid in additions)
        special['fourthBatchIdentitiesRecovered'] = True
    if 'school-images-b5' in str(overlay):
        assert len(additions) == 90 and len(batch['review']) == 120
        for cid in ('eng-pdf-v7-007', 'eng-dm-31-at', 'eng-dm21', 'eng-parm-family',
                    'eng-pdf-v7-023', 'grenade-dm51', 'pdf198-3-cf1a8ba4a02e'):
            assert final[cid] == old[cid], cid
        assert additions['pdf198-school5-dm31-charge']['categoryId'] == 'charges'
        assert additions['pdf198-school5-dm21a1-charge']['categoryId'] == 'charges'
        assert additions['pdf198-school5-dm12b1-charge']['categoryId'] == 'charges'
        assert not old['ordnance-v27-rbk-500']['images']
        assert not old['pdf198-8-ab3ec582c218']['images']
        assert final['ordnance-v27-rbk-500']['images'] and final['pdf198-8-ab3ec582c218']['images']
        for r in batch['review']:
            if 932 <= r['figureIndex'] <= 1018:
                assert r['cropBox'] == [0, 0, 900, 220]
                assert r['asset']['height'] == 220
        assert not {40, 58, 80, 84, 140, 173, 242, 254, 261, 265, 1161, 1017, 1018} & {r['figureIndex'] for r in batch['review']}
        special.update(minesAndChargesSeparated=True, uavPerformanceTablesExcluded=True,
                       uncertainVariantsExcluded=True, emptyGalleriesFilled=2)

    db = sqlite3.connect(database)
    try:
        assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        assert not db.execute('PRAGMA foreign_key_check').fetchall()
        db.execute("INSERT INTO cards_fts(cards_fts) VALUES ('integrity-check')")
        assert db.execute('SELECT count(*) FROM cards').fetchone()[0] == len(final)
        image_count = sum(len(c['images']) for c in final.values())
        assert db.execute('SELECT count(*) FROM images').fetchone()[0] == image_count
        for cid in set(changes) | set(additions):
            row = db.execute('SELECT rowid, searchText FROM cards WHERE id=?', (cid,)).fetchone()
            assert row and row[0] == final[cid]['rowid'] and row[1].strip()
            words = re.findall(r'[^\W_]+', row[1], re.UNICODE)
            matched = False
            for word in words[:8]:
                hit = db.execute('SELECT docid FROM cards_fts WHERE cards_fts MATCH ? AND docid=?',
                                 ('"'+word+'"', row[0])).fetchone()
                if hit:
                    matched = True
                    break
            assert matched, cid
    finally:
        db.close()
    return dict(integrity='ok', foreignKeys='ok', fts='ok', actualFtsQueries=len(changes)+len(additions),
                previousCardIdsAndRowidsPreserved=len(old), newCards=len(additions),
                existingCardsUpdated=len(changes), replacedGalleryRows=replacements,
                addedGalleryRows=len(batch['review'])-replacements, decodedAssetFiles=len(files),
                cardCount=len(final), imageCount=image_count, androidImportTested=False,
                published=False, **special)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ('baseline', 'catalog', 'database', 'overlay', 'report'):
        parser.add_argument('--'+name, required=True)
    args = parser.parse_args()
    result = verify(args.baseline, args.catalog, args.database, args.overlay)
    Path(args.report).write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(result, ensure_ascii=False))
