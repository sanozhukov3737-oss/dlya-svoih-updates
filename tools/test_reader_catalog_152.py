"""Preservation against the actual catalog-151 snapshot, not curated templates."""
import hashlib
import json
from pathlib import Path
import unittest
from rewrite_reader_v121 import table_blocks

ROOT=Path(__file__).resolve().parents[1]
DATA=json.loads((ROOT/'content/catalog.json').read_text())
CARDS={c['id']:c for c in DATA['cards']}
BASELINE=json.loads((ROOT/'tools/reader_151_baseline.json').read_text())
AUDIT=json.loads((ROOT/'docs/READER_152_AUDIT.json').read_text())
CHANGED={r['id'] for r in AUDIT['cards']}

class Reader152Tests(unittest.TestCase):
    def test_identity_and_complete_existing_provenance(self):
        self.assertEqual({r['id'] for r in BASELINE},set(CARDS))
        for row in BASELINE:
            c=CARDS[row['id']]
            identity={k:v for k,v in c.items() if k not in ('body','summary')}
            actual=hashlib.sha256(json.dumps(identity,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
            self.assertEqual(row['identity'],actual,c['id'])
            notes=c['body'].partition('\n\n## Служебные сведения')[2]
            self.assertEqual(row['notesHash'],hashlib.sha256(notes[:row['notesLength']].encode()).hexdigest(),c['id'])

    def test_quantities_tables_and_variant_qualifiers_remain_readable(self):
        for row in BASELINE:
            c=CARDS[row['id']]
            article,_,notes=c['body'].partition('\n\n## Служебные сведения')
            for quantity in row['measurements']:self.assertIn(quantity,article,c['id']+': '+quantity)
            expected=[v for v in row['tableValues'] if v not in row['archivedTableValues']]
            actual=[v for t in table_blocks(article) for k,v in t]
            self.assertEqual(expected,actual,c['id'])
            for value in row['archivedTableValues']:self.assertIn(value,notes,c['id'])

    def test_change_scope_and_medical_content(self):
        self.assertEqual(152,DATA['contentVersion'])
        self.assertEqual(75,len(CHANGED))
        changes=set()
        for row in BASELINE:
            c=CARDS[row['id']]
            changed=hashlib.sha256(c['body'].encode()).hexdigest()!=row['bodyHash']
            if changed:changes.add(c['id'])
            else:self.assertEqual(row['summary'],c['summary'],c['id'])
            if c['section']=='MEDICINE':self.assertFalse(changed,c['id'])
        self.assertEqual(CHANGED,changes)
        self.assertEqual(37,sum(c['categoryId'].startswith('mines-') for id,c in CARDS.items() if id in CHANGED))

if __name__=='__main__':unittest.main()
