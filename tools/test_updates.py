"""Host migration/media/package contract tests. Android importer is tested separately on device."""
import copy
import hashlib
import json
from pathlib import Path
import re
import shutil
import sqlite3
import tempfile
import unittest
import zipfile
from PIL import Image
from build_catalog import ROOT, ASSETS, normalize, validate
from build_pack import make_pack

DATA = json.loads((ROOT / 'content/catalog.json').read_text(encoding='utf-8'))
PRODUCTION_DB = ASSETS / 'database/guide-v29.db'

class UpdateTests(unittest.TestCase):
    def test_bundled_image_positions_pass_android_importer(self):
        with sqlite3.connect(PRODUCTION_DB) as db:
            invalid = db.execute('SELECT id, cardId, position FROM images WHERE position NOT BETWEEN 0 AND 11').fetchall()
        self.assertEqual([], invalid)

    def test_out_of_range_image_position_is_rejected(self):
        wrong = copy.deepcopy(DATA)
        card = next(card for card in wrong['cards'] if card['images'])
        card['images'][0]['position'] = 12
        with self.assertRaisesRegex(ValueError, 'Invalid image position'):
            validate(wrong)

    def test_production_migration_preserves_favorite_and_fts(self):
        kotlin = (ROOT / 'app/src/main/java/ru/dlyasvoih/app/data/local/GuideDatabase.kt').read_text()
        migration = re.findall(r'db\.execSQL\("([^"\n]+)"\)', kotlin)
        self.assertEqual(6, len(migration))
        with tempfile.TemporaryDirectory() as directory:
            old = Path(directory) / 'old.db'
            shutil.copyfile(ROOT / 'app/src/androidTest/assets/database/v1.db', old)
            with sqlite3.connect(old) as db, sqlite3.connect(PRODUCTION_DB) as current:
                db.execute('PRAGMA foreign_keys=ON')
                db.execute("INSERT INTO favorites VALUES ('first-aid-burn',1)")
                for statement in migration:
                    db.execute(statement)
                for table in ['cards','reading','favorites']:
                    self.assertEqual(current.execute(f'PRAGMA table_info({table})').fetchall(), db.execute(f'PRAGMA table_info({table})').fetchall())
                self.assertEqual([('first-aid-burn',1)], db.execute('SELECT * FROM favorites').fetchall())
                self.assertEqual(1, db.execute('SELECT COUNT(*) FROM cards_fts WHERE cards_fts MATCH ?', ('"проточ*"',)).fetchone()[0])
                self.assertFalse(db.execute('PRAGMA foreign_key_check').fetchall())

    def test_reading_survives_database_reopen_and_card_update(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'guide.db'
            shutil.copyfile(PRODUCTION_DB, path)
            with sqlite3.connect(path) as db:
                db.execute('PRAGMA foreign_keys=ON')
                db.execute("INSERT INTO reading VALUES ('first-aid-burn', 4, 72, 1000, 2)")
                db.execute("UPDATE cards SET summary='Тестовое изменение' WHERE id='first-aid-burn'")
            with sqlite3.connect(path) as db:
                self.assertEqual(('first-aid-burn',4,72,1000,2), db.execute('SELECT * FROM reading').fetchone())

    def test_bundled_version_marker_matches_database(self):
        with sqlite3.connect(PRODUCTION_DB) as db:
            self.assertEqual((ASSETS / 'database/content-version.txt').read_text().strip(),
                db.execute("SELECT value FROM metadata WHERE key='content_version'").fetchone()[0])

    def test_bundled_search_fields_match_catalog_text(self):
        with sqlite3.connect(PRODUCTION_DB) as db:
            rows = {
                card_id: (sort_title, search_text)
                for card_id, sort_title, search_text in
                db.execute('SELECT id, sortTitle, searchText FROM cards')
            }
        self.assertEqual(len(DATA['cards']), len(rows))
        for card in DATA['cards']:
            expected_search = normalize(' '.join([
                card['title'], card['summary'], card['body'], *card['tags']
            ]))
            self.assertEqual(normalize(card['title']), rows[card['id']][0], card['id'])
            self.assertEqual(expected_search, rows[card['id']][1], card['id'])

    def test_thumbnails_are_separate_and_bounded(self):
        for card in DATA['cards']:
            for item in card['images']:
                self.assertNotEqual(item['localPath'], item['thumbnailPath'])
                with Image.open(ASSETS / item['thumbnailPath']) as thumb, Image.open(ASSETS / item['localPath']) as full:
                    self.assertLessEqual(max(thumb.size),256)
                    self.assertLessEqual(max(full.size),1600)
                    self.assertLess((ASSETS / item['thumbnailPath']).stat().st_size, (ASSETS / item['localPath']).stat().st_size)

    def test_wrong_dimensions_and_missing_thumbnail_are_rejected(self):
        wrong=copy.deepcopy(DATA);wrong['cards'][1]['images'][0]['width']=100
        with self.assertRaises(ValueError): validate(wrong)
        wrong=copy.deepcopy(DATA);wrong['cards'][1]['images'][0]['thumbnailPath']='thumbs/missing.webp'
        with self.assertRaises(ValueError): validate(wrong)

    def test_pack_manifest_hashes_all_files_and_has_no_user_data(self):
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/'pack.zip'
            make_pack(ROOT / 'content/catalog.json', output)
            with zipfile.ZipFile(output) as archive:
                manifest=json.loads(archive.read('manifest.json'))
                self.assertEqual(DATA['contentVersion'],manifest['contentVersion'])
                self.assertEqual(set(archive.namelist()),{'manifest.json'}|{item['path'] for item in manifest['files']})
                for item in manifest['files']:
                    data=archive.read(item['path'])
                    self.assertEqual(len(data),item['bytes'])
                    self.assertEqual(hashlib.sha256(data).hexdigest(),item['sha256'])
                db_path=Path(directory)/'check.db';db_path.write_bytes(archive.read('guide.db'))
                with sqlite3.connect(db_path) as db:
                    self.assertEqual(0,db.execute('SELECT COUNT(*) FROM favorites').fetchone()[0])
                    self.assertEqual(0,db.execute('SELECT COUNT(*) FROM reading').fetchone()[0])

if __name__ == '__main__': unittest.main(verbosity=2)
