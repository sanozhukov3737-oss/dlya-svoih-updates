"""Validate the shipped display asset, its credits, and exact catalog attachment."""
import hashlib
import json
from pathlib import Path
import sqlite3
import struct
import unittest
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'app/src/main/assets/viewer3d'

class OfflineModelTests(unittest.TestCase):
    def test_every_manifest_model_is_self_contained_and_has_valid_credits(self):
        models = json.loads((ASSETS / 'models.json').read_text())['models']
        self.assertGreaterEqual(len(models), 15)
        self.assertEqual(len(models), len({m['id'] for m in models}))
        self.assertEqual(len(models), len({m['file'] for m in models}))
        cards = set()
        for item in models:
            with self.subTest(model=item['id']):
                self.assertRegex(item['file'], r'^[a-z0-9-]+\.glb$')
                self.assertEqual('CC BY 4.0', item['license'])
                self.assertEqual('https://creativecommons.org/licenses/by/4.0/', item['licenseUrl'])
                source = urlparse(item['source'])
                self.assertEqual('https', source.scheme)
                self.assertIn(source.hostname, ('sketchfab.com', 'www.printables.com'))
                self.assertTrue(source.path.startswith('/3d-models/') if source.hostname == 'sketchfab.com' else source.path.startswith('/model/'))
                self.assertTrue(item['author'] and item['modifications'])
                self.assertFalse(cards.intersection(item['cardIds']))
                cards.update(item['cardIds'])
                raw = (ASSETS / item['file']).read_bytes()
                self.assertEqual(item['bytes'], len(raw))
                self.assertEqual(item['packagedSha256'], hashlib.sha256(raw).hexdigest())
                self.assertEqual((b'glTF', 2, len(raw)), struct.unpack_from('<4sII', raw))
                size = struct.unpack_from('<I', raw, 12)[0]
                model = json.loads(raw[20:20+size])
                self.assertEqual(1, len(model['buffers']))
                self.assertNotIn('uri', model['buffers'][0])
                self.assertFalse(model.get('extensionsRequired'))
                self.assertTrue(model['meshes'])
                for image in model.get('images', []):
                    self.assertNotIn('uri', image)
                    self.assertIn(image['mimeType'], ('image/png', 'image/jpeg'))
                binary_size = struct.unpack_from('<I', raw, 20+size)[0]
                for view in model['bufferViews']:
                    self.assertEqual(0, view.get('buffer', 0))
                    self.assertLessEqual(view.get('byteOffset', 0) + view['byteLength'], binary_size)

    def test_exact_card_bindings_exclude_other_variants_and_unrelated_m18_grenade(self):
        models = json.loads((ASSETS / 'models.json').read_text())['models']
        with sqlite3.connect('file:'+str(ROOT/'app/src/main/assets/database/guide-v29.db')+'?mode=ro', uri=True) as db:
            for model in models:
                for card_id in model['cardIds']:
                    row = db.execute('SELECT title,categoryId FROM cards WHERE id=?', (card_id,)).fetchone()
                    self.assertIsNotNone(row, (model['id'], card_id))
                    self.assertTrue(row[1].startswith('mines-'), row)
        ids = {card for model in models for card in model['cardIds']}
        self.assertNotIn('ordnance-v29-ga-0158', ids)
        self.assertNotIn('ref-v8-tmn-46', ids)
        self.assertNotIn('mine-audit-v25-su-pfm-1s', ids)
        self.assertFalse(next(m for m in models if m['id'] == 'tm-62-family')['cardIds'])
        self.assertEqual(['mine-audit-v25-su-pmk-40'], next(m for m in models if m['id'] == 'pmk-40')['cardIds'])
        self.assertEqual(['eng-pdf-v7-125'], next(m for m in models if m['id'] == 'smi-35')['cardIds'])

    def test_packaged_glb_is_self_contained_and_all_buffers_are_valid(self):
        raw = (ASSETS / 'tm-46.glb').read_bytes()
        self.assertEqual((b'glTF', 2, len(raw)), struct.unpack_from('<4sII', raw))
        size, kind = struct.unpack_from('<II', raw, 12)
        self.assertEqual(0x4e4f534a, kind)
        model = json.loads(raw[20:20+size])
        binary_size, binary_kind = struct.unpack_from('<II', raw, 20+size)
        self.assertEqual(0x004e4942, binary_kind)
        self.assertEqual(len(raw), 28+size+binary_size)
        self.assertEqual(1, len(model['buffers']))
        self.assertNotIn('uri', model['buffers'][0])
        self.assertLessEqual(model['buffers'][0]['byteLength'], binary_size)
        self.assertFalse(model.get('extensionsRequired'))
        self.assertEqual(4, len(model['meshes']))
        self.assertEqual(4, len(model['images']))
        for image in model['images']:
            self.assertNotIn('uri', image)
            self.assertIn(image['mimeType'], ('image/png', 'image/jpeg'))
            self.assertLess(image['bufferView'], len(model['bufferViews']))
        for view in model['bufferViews']:
            self.assertEqual(0, view.get('buffer', 0))
            self.assertEqual(0, view.get('byteOffset', 0) % 4)
            self.assertGreater(view['byteLength'], 0)
            self.assertLessEqual(view.get('byteOffset', 0)+view['byteLength'], binary_size)
        for accessor in model['accessors']:
            self.assertLess(accessor['bufferView'], len(model['bufferViews']))
            self.assertGreater(accessor['count'], 0)

    def test_asset_identity_license_and_card_are_preserved(self):
        credits = json.loads((ASSETS / 'model-credits.json').read_text())
        value = (ASSETS / 'tm-46.glb').read_bytes()
        self.assertEqual(credits['packagedSha256'], hashlib.sha256(value).hexdigest())
        self.assertEqual(credits['bytes'], len(value))
        self.assertEqual('Oscar Goldsworthy', credits['author'])
        self.assertEqual('CC BY 4.0', credits['license'])
        self.assertTrue(credits['modifications'])
        self.assertEqual('ref-v8-tm-46', credits['cardId'])
        with sqlite3.connect('file:'+str(ROOT/'app/src/main/assets/database/guide-v29.db')+'?mode=ro', uri=True) as db:
            self.assertEqual(('ТМ-46',), db.execute('SELECT title FROM cards WHERE id=?', (credits['cardId'],)).fetchone())

if __name__ == '__main__':
    unittest.main()
