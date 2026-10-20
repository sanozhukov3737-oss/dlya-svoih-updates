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
EDITOR_NOTES=json.loads((ROOT/'docs/READER_ARCHIVED_EDITOR_NOTES.json').read_text())
FACT_CORRECTIONS=json.loads((ROOT/'docs/READER_FACT_CORRECTIONS.json').read_text())
ADDED_FACT_ROWS=json.loads((ROOT/'docs/READER_ADDED_FACT_ROWS.json').read_text())
COUNTRY_TEXT_CORRECTIONS=json.loads((ROOT/'docs/READER_COUNTRY_TEXT_CORRECTIONS.json').read_text())

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
            archived=row['archivedTableValues']+EDITOR_NOTES.get(c['id'],[])
            expected=[v for v in row['tableValues'] if v not in archived]
            for correction in FACT_CORRECTIONS.get(c['id'],[]):
                expected=[correction['new'] if v==correction['old'] else v for v in expected]
                self.assertIn(correction['old'],notes,c['id'])
                self.assertTrue(correction['url'].startswith('https://'),c['id'])
            for extra in ADDED_FACT_ROWS.get(c['id'],[]):
                expected.append(extra['value'])
                self.assertIn(extra['value'],notes,c['id'])
            actual=[v for t in table_blocks(article) for k,v in t]
            self.assertEqual(expected,actual,c['id'])
            for value in archived:self.assertIn(value,notes,c['id'])
            for correction in COUNTRY_TEXT_CORRECTIONS.get(c['id'],[]):
                self.assertIn('## Страна и происхождение\n\n'+correction['new'],article,c['id'])
                self.assertIn('## Страна и происхождение\n\n'+correction['old'],notes,c['id'])
                self.assertTrue(correction['url'].startswith('https://'),c['id'])

    def test_change_scope_and_medical_content(self):
        self.assertEqual(152,DATA['contentVersion'])
        self.assertEqual(1273,len(CHANGED))
        changes=set()
        for row in BASELINE:
            c=CARDS[row['id']]
            changed=hashlib.sha256(c['body'].encode()).hexdigest()!=row['bodyHash']
            if changed:changes.add(c['id'])
            else:self.assertEqual(row['summary'],c['summary'],c['id'])
            if c['section']=='MEDICINE':
                self.assertTrue(changed,c['id'])
                self.assertIn('Переработка медицинской памятки',c['body'],c['id'])
                self.assertIn('Текст требует проверки медицинским редактором',c['body'].partition('\n\n## Служебные сведения')[2],c['id'])
        self.assertEqual(CHANGED,changes)
        self.assertEqual(522,sum(c['categoryId'].startswith('mines-') for id,c in CARDS.items() if id in CHANGED))

if __name__=='__main__':unittest.main()
