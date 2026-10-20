"""Check aligned fields and the real Room comparison query, including wrong-category family IDs."""
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class QuickComparisonTests(unittest.TestCase):
    def test_labels_order_missing_values_variants_and_full_table(self):
        java = shutil.which('java')
        self.assertIsNotNone(java)
        sources = [ROOT / f'app/src/main/java/ru/dlyasvoih/app/ui/content/{name}.java'
                   for name in ('ReferenceBodyParser', 'ReaderContent', 'ComparisonContent')]
        sources.append(ROOT / 'test-common/HostComparisonChecks.java')
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([java, '-m', 'jdk.compiler/com.sun.tools.javac.Main', '-d', directory,
                                     *map(str, sources)], capture_output=True, text=True, timeout=30)
            self.assertEqual(0, result.returncode, result.stderr)
            result = subprocess.run([java, '-cp', directory, 'ru.dlyasvoih.app.ui.content.HostComparisonChecks'],
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(0, result.returncode, result.stderr)

    def test_comparison_never_crosses_categories_or_sections(self):
        dao = (ROOT / 'app/src/main/java/ru/dlyasvoih/app/data/local/GuideDao.kt').read_text()
        query = re.search(r'@Query\("""((?:(?!""").)*)"""\)\s*fun comparisonCards', dao, re.S).group(1)

        def compare(db, current, family):
            sql = query.replace(':familyIds', ','.join('?' for _ in family) if family else 'NULL').replace(':id', '?')
            params = []
            for match in re.finditer(r':id|:familyIds', query):
                params.extend([current] if match.group() == ':id' else family)
            return db.execute(sql, params).fetchall()

        with sqlite3.connect(':memory:') as db:
            db.execute('CREATE TABLE cards(id TEXT, section TEXT, categoryId TEXT, archived INT, sortTitle TEXT)')
            db.execute('CREATE TABLE card_countries(cardId TEXT, countryId TEXT)')
            db.executemany('INSERT INTO cards VALUES(?,?,?,?,?)', [
                ('current', 'S1', 'C1', 0, 'a'), ('correct', 'S1', 'C1', 0, 'b'),
                ('wrong-category', 'S1', 'C2', 0, 'c'), ('wrong-section', 'S2', 'C1', 0, 'd'),
                ('archived', 'S1', 'C1', 1, 'e')])
            self.assertEqual(['correct'], [r[0] for r in compare(db, 'current',
                ['current', 'correct', 'wrong-category', 'wrong-section', 'archived'])])
        with sqlite3.connect(ROOT / 'app/src/main/assets/database/guide-v29.db') as db:
            for current, section, category in db.execute('SELECT id,section,categoryId FROM cards'):
                rows = compare(db, current, ['eng-pmn', 'grenade-rgn', 'first-aid-burn'])
                # Entity rows begin with rowid, id, section, categoryId.
                self.assertTrue(all(r[1] != current and r[2:4] == (section, category) for r in rows), current)


if __name__ == '__main__':
    unittest.main()
