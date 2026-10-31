"""Check the saved image-only catalog candidate against the public 198 source."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import zipfile
from PIL import Image
from build_update_feed import describe_pack
from restore_catalog199_candidate import EXPECTED_SHA256, EXPECTED_BYTES, ROOT

def rows(db, table):
    db.row_factory = sqlite3.Row
    return {r['id']: dict(r) for r in db.execute('SELECT * FROM '+table)}

def verify(pack, baseline, output):
    output.mkdir(parents=True, exist_ok=True)
    feed = describe_pack(pack, 'https://github.com/sanozhukov3737-oss/dlya-svoih-updates/releases/download/catalog-199/catalog-199.zip')
    assert (feed['sha256'], feed['bytes'], feed['contentVersion']) == (EXPECTED_SHA256, EXPECTED_BYTES, 199)
    with zipfile.ZipFile(pack) as archive:
        candidate = output / 'candidate.db'
        candidate.write_bytes(archive.read('guide.db'))
        with sqlite3.connect(baseline) as old, sqlite3.connect(candidate) as new:
            assert old.execute("SELECT value FROM metadata WHERE key='content_version'").fetchone() == ('198',)
            assert new.execute("SELECT value FROM metadata WHERE key='content_version'").fetchone() == ('199',)
            assert new.execute('PRAGMA integrity_check').fetchone() == ('ok',)
            assert not new.execute('PRAGMA foreign_key_check').fetchall()
            schema = "SELECT type,name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name"
            assert old.execute(schema).fetchall() == new.execute(schema).fetchall()
            old_cards, new_cards = rows(old, 'cards'), rows(new, 'cards')
            assert len(old_cards) == len(new_cards) == 2855
            assert old_cards.keys() == new_cards.keys()
            for key, before in old_cards.items():
                after = new_cards[key]
                assert {k:v for k,v in before.items() if k != 'thumbnailPath'} == {k:v for k,v in after.items() if k != 'thumbnailPath'}, key
            for table in ('countries', 'categories', 'card_countries'):
                assert sorted(map(tuple, old.execute('SELECT * FROM '+table))) == sorted(map(tuple, new.execute('SELECT * FROM '+table)))
            old_images, new_images = rows(old, 'images'), rows(new, 'images')
            old_sources, new_sources = rows(old, 'sources'), rows(new, 'sources')
            assert len(old_images) == 2317 and len(new_images) == 2403
            assert len(old_sources) == 6861 and len(new_sources) == 6988
            for key, row in old_images.items(): assert row == new_images[key], key
            for key, row in old_sources.items(): assert row == new_sources[key], key
            for table in ('favorites', 'reading'):
                assert new.execute('SELECT COUNT(*) FROM '+table).fetchone()[0] == 0
            added = [dict(row) for key,row in new_images.items() if key not in old_images]
            assert len(added) == 86 and len({row['cardId'] for row in added}) == 78
            def units(text): return len(text.encode('utf-16-le'))//2
            for row in new_images.values():
                assert units(row['caption']) <= 600 and 0 <= row['position'] <= 11
            assert not new.execute('SELECT cardId FROM images GROUP BY cardId HAVING COUNT(*) > 12').fetchall()
            for row in new_sources.values():
                assert units(row['title']) <= 500
                assert row['url'] is None or row['url'].startswith('https://') and units(row['url']) <= 2048
            for row in new_images.values():
                with Image.open(io.BytesIO(archive.read(row['localPath']))) as image:
                    image.load()
                    assert image.size == (row['width'],row['height'])
                    assert max(image.size) <= 1600
            manifest = json.loads(archive.read('manifest.json'))
            manifest_paths = {r['path'] for r in manifest['files']}
            decoded = 0
            for name in archive.namelist():
                if name.startswith(('images/', 'thumbs/')):
                    with Image.open(io.BytesIO(archive.read(name))) as image:
                        image.load()
                        assert max(image.size) <= (256 if name.startswith('thumbs/') else 1600)
                    decoded += 1
            assert decoded == 4766
            source = json.loads((ROOT/'content/catalog.json').read_text())
            assert source['contentVersion'] == 198
            old_media = {image[k] for card in source['cards'] for image in card['images'] for k in ('localPath','thumbnailPath')}
            assert len(old_media) == 4594
            for name in old_media:
                assert name in manifest_paths and archive.read(name) == (ROOT/'app/src/main/assets'/name).read_bytes(), name
            fixtures = dict(newImages=added, changedThumbnails=[dict(cardId=key,path=row['thumbnailPath'])
                for key,row in new_cards.items() if row['thumbnailPath'] != old_cards[key]['thumbnailPath']])
            (output/'image-fixtures.json').write_text(json.dumps(fixtures,separators=(',',':'))+'\n')
            digest = hashlib.sha256(candidate.read_bytes()).hexdigest()
            assert digest == '7e08f4d4bf1b46debd8cc35e68f0b3e36c2d9d8687eca8ab2075f4aee0052fd9'
    report = dict(contentVersion=199, cards=2855, images=2403, addedImages=86, affectedCards=78,
        addedSources=127, previousCardsPreserved=2855, previousImagesPreserved=2317,
        previousSourcesPreserved=6861, previousMediaFilesPreserved=4594, decodedMediaFiles=decoded,
        bytes=EXPECTED_BYTES, sha256=EXPECTED_SHA256, databaseSha256=digest,
        exactSavedCandidate=True, integrityCheck='ok', foreignKeyViolations=0, userDataRows=0)
    (output/'package-verification.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))
    return report

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pack',type=Path,required=True)
    parser.add_argument('--baseline',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    verify(args.pack,args.baseline,args.output)
