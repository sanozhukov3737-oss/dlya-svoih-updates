"""Prevent category illustrations from disappearing during catalog restoration."""
from pathlib import Path
import re
import sqlite3
import unittest

ROOT = Path(__file__).resolve().parents[1]


class MenuImagesTest(unittest.TestCase):
    def test_all_menu_photos_are_application_resources(self):
        source = (ROOT / 'app/src/main/java/ru/dlyasvoih/app/ui/screens/CatalogMenuIcon.kt').read_text()
        resources = set(re.findall(r'photo = R\.drawable\.(\w+)', source))
        self.assertEqual(7, len(resources))
        self.assertNotIn('assetPath', source)
        for resource in resources:
            data = (ROOT / 'app/src/main/res/drawable-nodpi' / (resource + '.webp')).read_bytes()
            self.assertEqual(b'RIFF', data[:4], resource)
            self.assertEqual(b'WEBP', data[8:12], resource)
            self.assertGreater(len(data), 100, resource)

    def test_catalog_media_paths_still_exist(self):
        assets = ROOT / 'app/src/main/assets'
        with sqlite3.connect(assets / 'database/guide-v29.db') as db:
            paths = db.execute('SELECT localPath FROM images UNION SELECT thumbnailPath FROM cards '
                               'WHERE thumbnailPath IS NOT NULL').fetchall()
        self.assertTrue(paths)
        for (path,) in paths:
            self.assertTrue((assets / path).is_file(), path)


if __name__ == '__main__':
    unittest.main()
