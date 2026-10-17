"""Exercise the production Java search SQL against the shipped catalog, including a damaged FTS index."""
import base64
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]

class CatalogSearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.java = shutil.which('java')
        if cls.java is None: raise unittest.SkipTest('JDK is unavailable')
        cls.directory = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.directory.cleanup)
        sources = ['app/src/main/java/ru/dlyasvoih/app/data/CatalogSearch.java', 'test-common/HostSearchChecks.java']
        subprocess.run([cls.java, '-m', 'jdk.compiler/com.sun.tools.javac.Main', '-d', cls.directory.name,
                        *[str(ROOT/p) for p in sources]], check=True, capture_output=True, timeout=30)
        cls.db = sqlite3.connect(':memory:')
        cls.addClassCleanup(cls.db.close)
        with sqlite3.connect(ROOT/'app/src/main/assets/database/guide-v29.db') as source: source.backup(cls.db)

    def plan(self, query):
        output = subprocess.check_output([self.java, '-cp', self.directory.name,
                    'ru.dlyasvoih.app.data.HostSearchChecks', query], text=True, timeout=10).splitlines()
        it = iter(output)
        where = base64.b64decode(next(it)).decode()
        args = [base64.b64decode(next(it)).decode() for _ in range(int(next(it))) ]
        rank = base64.b64decode(next(it)).decode()
        args += [base64.b64decode(next(it)).decode() for _ in range(int(next(it))) ]
        return where, rank, args

    def results(self, query):
        where, rank, args = self.plan(query)
        return self.db.execute('SELECT c.id,c.title FROM cards c WHERE c.archived=0 AND '+where+
                               ' ORDER BY '+rank+', c.sortTitle,c.rowid', args).fetchall()

    def test_model_spellings_put_the_actual_card_first(self):
        for query in ['ТМ-46', 'ТМ46', 'TM-46', 'TM46', 'тм 46', 'ТM‑46', 'ТМ–46']:
            with self.subTest(query=query):
                rows = self.results(query)
                self.assertTrue(rows)
                self.assertEqual('ref-v8-tm-46', rows[0][0])

    def test_number_search_prioritizes_names_over_body_mentions(self):
        rows = self.results('46')
        target = [i for i,r in enumerate(rows) if r[0]=='ref-v8-tm-46']
        self.assertTrue(target)
        self.assertLess(target[0], 3)
        print('46 first results:', rows[:5])

    def test_other_model_names_and_full_text_continue_to_work(self):
        for query in ['ПМН-2','PMN2','РГД-5','RGD5','ПТАБ-2.5','PTAB2.5']:
            with self.subTest(query=query): self.assertTrue(self.results(query), query)
        self.assertIn('first-aid-burn',[r[0] for r in self.results('проточной')])

    def test_title_search_survives_a_missing_fts_entry(self):
        row = self.db.execute("SELECT rowid FROM cards WHERE id='ref-v8-tm-46'").fetchone()[0]
        self.db.execute('SAVEPOINT damaged_index')
        try:
            self.db.execute('DELETE FROM cards_fts WHERE docid=?',(row,))
            self.assertEqual('ref-v8-tm-46',self.results('TM46')[0][0])
        finally:
            self.db.execute('ROLLBACK TO damaged_index')
            self.db.execute('RELEASE damaged_index')

    def test_standalone_numbers_are_not_numeric_prefixes(self):
        where, rank, args = self.plan('46')
        self.db.execute('SAVEPOINT probes')
        try:
            # Clone a valid row without touching any real catalog card or its saved data.
            self.db.execute("INSERT INTO cards SELECT 2000001,'search-probe-460',section,categoryId,'Probe-460','probe','probe','', 'probe-460','probe 460',NULL,contentStatus,reviewedAt,0,modelStatus,sourceGrade,verifiedAt FROM cards LIMIT 1")
            self.assertNotIn('search-probe-460',[r[0] for r in self.results('46')])
        finally:
            self.db.execute('ROLLBACK TO probes');self.db.execute('RELEASE probes')

    def test_sql_bindings_and_normalization(self):
        output = subprocess.check_output([self.java,'-cp',self.directory.name,'ru.dlyasvoih.app.data.HostSearchChecks'],text=True)
        self.assertIn('checks passed',output)

if __name__=='__main__': unittest.main()
