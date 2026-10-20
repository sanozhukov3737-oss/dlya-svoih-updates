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

    def test_punctuated_designations_work_without_dots(self):
        for query in ['S.Mi.35', 'SMi35', 'smi-35']:
            with self.subTest(query=query):
                self.assertEqual('eng-pdf-v7-125', self.results(query)[0][0])
        self.assertEqual('mine-audit-v25-su-pmk-40', self.results('PMK40')[0][0])
        self.assertNotIn('eng-pdf-v7-125', [r[0] for r in self.results('SMi350')])

    def test_other_model_names_and_full_text_continue_to_work(self):
        for query in ['ПМН-2','PMN2','РГД-5','RGD5','ПТАБ-2.5','PTAB2.5']:
            with self.subTest(query=query): self.assertTrue(self.results(query), query)
        self.assertIn('first-aid-burn',[r[0] for r in self.results('проточной')])
        self.assertIn('first-aid-burn',[r[0] for r in self.results('проточной водой')])

    def test_uav_designations_and_russian_latin_aliases(self):
        spellings = {
            'ofsp-05': ['ОФСП-05', 'ОФСП05', 'OFSP05', 'ОФСП-0,5'],
            'ofsp-08': ['ОФСП-08', 'ОФСП08', 'OFSP08', 'ОФСП-0,8'],
            'ofsp-17': ['ОФСП-1,7', 'ОФСП-1.7', 'OFSP1.7'],
            'ofsp-25': ['ОФСП-2,5', 'ОФСП-2.5', 'OFSP2.5'],
            'ofbch-2': ['ОФБЧ-2', 'OFBCh2'],
            'ofbch-25': ['ОФБЧ-2,5', 'ОФБЧ-2.5', 'OFBCh2.5'],
            'ibm-02': ['ИБМ-0,2', 'ІБМ-0,2', 'IBM-0.2'],
            'ibm-05': ['ИБМ-0,5', 'ІБМ-0,5', 'IBM-0.5'],
            'ibm-1': ['ИБМ-1', 'IBM1'],
            'ibm-3': ['ИБМ-3', 'IBM3'],
            'ss-02': ['СС-0,2', 'СС0.2', 'SS-02'],
            'ss-05': ['СС-0,5', 'СС0.5', 'SS-05'],
            'ss-mpp-3': ['СС-МПП-3', 'ССМПП3', 'SS-MPP-3'],
        }
        for suffix, queries in spellings.items():
            for query in queries:
                with self.subTest(query=query):
                    self.assertIn('uavref-' + suffix, [r[0] for r in self.results(query)])

    def test_demz_variants_and_components_are_searchable_separately(self):
        queries = {
            'МВЧ62Д': 'mvch62d', 'MPEM1': 'mpem1', 'UZRGM2E': 'uzrgm2e',
            'RGD5E': 'rgd5e', 'MON502M': 'mon50-2m', 'ОЗМ72МС': 'ozm72ms',
            'ДІДБАБАЙ': 'didbabai', 'ММ-120СТ': 'mm120st',
            'МОА-VIY-1200нК': 'moa-viy-1200-nk', 'SRM523': 'motor-srm-523',
            'M121': 'm121', 'Праймер M82': 'primer-m82',
            'Корпус 155-мм снаряда М795': 'shell-hull-m795',
        }
        for query, suffix in queries.items():
            with self.subTest(query=query):
                self.assertIn('demzref-' + suffix, [r[0] for r in self.results(query)])

    def test_handbook_suffixes_and_identical_names_are_searchable(self):
        queries = {
            'ПНУ1-36': 'pnu-1-36',
            'MAB-L68K-VR1': 'mab-l68k-vr1',
            'HFB0500C': 'hfb0500c-morkov',
            'ОФБЧ-2.5 Маяк': 'ofbch-2-5-mayak-perspektiva',
            'РБ10-01': 'rb10-01', 'РБ10-02': 'rb10-02',
            'B61.00.08E': 'ub-3-v61-00-08e',
            'DF.FBP-16-T': 'df-fbp-16-t',
        }
        for query, suffix in queries.items():
            with self.subTest(query=query):
                self.assertIn('handbookref-' + suffix, [r[0] for r in self.results(query)])
        self.assertIn('uavref-ofbch-25', [r[0] for r in self.results('ОФБЧ-2,5')])

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
