"""Collection integrity, byte preservation, card identity and attribution."""
import hashlib
import json
from pathlib import Path
import sqlite3
import struct
import unittest

ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/'app/src/main/assets/viewer3d'
MODELS=json.loads((ASSETS/'models.json').read_text())['models']

class CollectionTests(unittest.TestCase):
    def test_exact_inventory_and_self_contained_glbs(self):
        self.assertEqual(615,len(MODELS))
        self.assertEqual(615,len({m['id'] for m in MODELS}))
        self.assertEqual(615,len({m['file'] for m in MODELS}))
        for m in MODELS:
            with self.subTest(model=m['id']):
                raw=(ASSETS/m['file']).read_bytes()
                self.assertEqual(m['packagedSha256'],hashlib.sha256(raw).hexdigest())
                self.assertEqual((b'glTF',2,len(raw)),struct.unpack_from('<4sII',raw))
                length,kind=struct.unpack_from('<II',raw,12)
                self.assertEqual(0x4e4f534a,kind)
                gltf=json.loads(raw[20:20+length])
                self.assertTrue(gltf['meshes'])
                for record in gltf.get('buffers',[])+gltf.get('images',[]):
                    self.assertNotIn('uri',record)
                self.assertIn(m['displayColorMode'],('source','illustrative'))
                self.assertTrue(m['author'] and m['license'] and m['displayNote'])

    def test_index_matches_real_cards_and_unconfirmed_models_are_separate(self):
        index=json.loads((ASSETS/'card-index.json').read_text())
        ids={c for m in MODELS for c in m['cardIds']}
        self.assertEqual(511,len(ids))
        self.assertEqual(sorted(ids),index)
        with sqlite3.connect('file:'+str(ROOT/'app/src/main/assets/database/guide-v29.db')+'?mode=ro',uri=True) as db:
            self.assertEqual(1695,db.execute('select count(*) from cards').fetchone()[0])
            for c in ids:
                row=db.execute('select categoryId from cards where id=?',(c,)).fetchone()
                self.assertIsNotNone(row,c)
                self.assertTrue(row[0].startswith('mines-'),c)
        for m in MODELS:
            if m.get('exactVariantIdentityConfirmed') is False or m.get('status')=='concept_candidate':
                self.assertFalse(m['cardIds'],m['id'])

    def test_input_contract_preserves_original_bytes(self):
        request=json.loads((ROOT/'docs/releases/app-0.3.138-inputs.json').read_text())
        self.assertEqual(596,len(request['newFiles']))
        for m in MODELS[19:]:
            self.assertEqual(request['newFiles'][m['file']],m['packagedSha256'])
        self.assertEqual(request['databaseSha256'],hashlib.sha256((ROOT/'app/src/main/assets/database/guide-v29.db').read_bytes()).hexdigest())

if __name__=='__main__': unittest.main()
