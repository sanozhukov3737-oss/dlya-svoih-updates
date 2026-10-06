"""Whole-catalog editorial boundaries against the actual catalog-150 snapshot."""
import hashlib
import json
from pathlib import Path
import sqlite3
import unittest
from rewrite_reader_v121 import READY, strip_table_citations, table_blocks

ROOT=Path(__file__).resolve().parents[1]
DATA=json.loads((ROOT/'content/catalog.json').read_text())
CARDS={c['id']:c for c in DATA['cards']}
BASELINE=json.loads((ROOT/'tools/reader_150_baseline.json').read_text())


class Reader151Tests(unittest.TestCase):
    def test_identity_numbers_and_existing_provenance_are_preserved(self):
        self.assertEqual(set(CARDS),{r['id'] for r in BASELINE})
        for row in BASELINE:
            c=CARDS[row['id']]
            identity={k:v for k,v in c.items() if k not in ('body','summary')}
            self.assertEqual(row['identity'],hashlib.sha256(json.dumps(identity,ensure_ascii=False,sort_keys=True).encode()).hexdigest(),c['id'])
            article,_,notes=c['body'].partition('\n\n## Служебные сведения')
            for value in row['measurements']:self.assertIn(value,article,c['id']+': '+value)
            self.assertEqual(row['notes'],hashlib.sha256(notes[:row['notesLength']].encode()).hexdigest(),c['id'])
            if row['protectedBody']:
                self.assertEqual(row['protectedBody'],hashlib.sha256(c['body'].encode()).hexdigest(),c['id'])
                self.assertEqual(row['protectedSummary'],c['summary'],c['id'])

    def test_table_facts_keep_order_and_all_variant_qualifiers(self):
        for row in BASELINE:
            c=CARDS[row['id']]
            article=c['body'].split('\n\n## Служебные сведения')[0]
            expected=row['tableValues']
            if not row['protectedBody']:
                expected=[strip_table_citations(value,[]).strip() for value in expected]
            actual=[v for table in table_blocks(article) for k,v in table]
            self.assertEqual(expected,actual,c['id'])

    def test_catalog_database_and_audit_agree_on_final_batch(self):
        audit=json.loads((ROOT/'docs/READER_151_AUDIT.json').read_text())
        self.assertEqual(151,DATA['contentVersion'])
        rows={r['id']:r for r in audit['cards']}
        self.assertEqual(1253,len(rows))
        self.assertEqual(set(CARDS)-READY-{c['id'] for c in CARDS.values() if c['section']=='MEDICINE'},set(rows))
        self.assertEqual(audit['bodyChanges'],sum(r['bodyChanged'] for r in rows.values()))
        with sqlite3.connect(ROOT/'app/src/main/assets/database/guide-v29.db') as db:
            database=dict(db.execute('SELECT id, body FROM cards'))
            self.assertEqual({id:c['body'] for id,c in CARDS.items()},database)

    def test_editorial_archive_and_known_broken_phrases_are_not_reader_text(self):
        for c in CARDS.values():
            if c['section']=='MEDICINE' or c['id'] in READY:continue
            article=c['body'].split('\n\n## Служебные сведения')[0]
            for broken in ('сведения о наполнении:', 'MN-123 — польская противотанковая мина, которой посвящена основная статья на В',
                           'относящаяся к вариант семейства','принято на вооружение в 1994 годом',
                           'Массу изделия 497 кг.', 'Массу снаряда 45 г;', 'Текущая версия каталога 26'):
                self.assertNotIn(broken,article,c['id'])

if __name__=='__main__':unittest.main()
