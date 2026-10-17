"""Validate the shipped display asset, its credits, and exact catalog attachment."""
import hashlib
import json
from pathlib import Path
import sqlite3
import struct
import unittest

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'app/src/main/assets/viewer3d'

class OfflineModelTests(unittest.TestCase):
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
