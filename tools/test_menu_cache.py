"""Check cached country totals against the existing direct menu query on real data."""
from pathlib import Path
import re
import sqlite3
import unittest

ROOT = Path(__file__).resolve().parents[1]
DAO = ROOT / 'app/src/main/java/ru/dlyasvoih/app/data/local/GuideDao.kt'


def query(method):
    source = DAO.read_text(encoding='utf-8')
    prefix = source[:source.index('    fun ' + method + '(')]
    return list(re.finditer(r'@Query\("""(.*?)"""\)', prefix, re.S))[-1].group(1)


class MenuCacheTest(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        with sqlite3.connect(ROOT / 'app/src/main/assets/database/guide-v29.db') as source:
            source.backup(self.db)

    def tearDown(self):
        self.db.close()

    def assert_all_menus(self):
        totals = self.db.execute(query('menuCountryTotals')).fetchall()
        names = {row[0]: row[1:] for row in self.db.execute('SELECT id,name,sortOrder FROM countries')}
        sections = [''] + [row[0] for row in self.db.execute('SELECT DISTINCT section FROM categories')]
        categories = [''] + [row[0] for row in self.db.execute('SELECT id FROM categories')]
        for section in sections:
            for category in categories:
                counts = {}
                for row_section, row_category, country, count in totals:
                    if (not section or row_section == section) and (not category or row_category == category):
                        counts[country] = counts.get(country, 0) + count
                actual = []
                for country, count in counts.items():
                    name, order = ('СССР / Россия', -1) if country == '@ru-su' else names[country]
                    actual.append((country, name, order, count))
                actual.sort(key=lambda row: (row[2], row[0]))
                expected = self.db.execute(query('countryChoices'), dict(section=section, category=category,
                    favoritesOnly=0, historyOnly=0)).fetchall()
                self.assertEqual(expected, actual, (section, category))

    def test_cached_totals_match_every_section_and_category(self):
        self.assert_all_menus()

    def test_archived_cards_and_two_country_links_do_not_inflate_counts(self):
        card = self.db.execute("SELECT id FROM cards WHERE archived=0 AND categoryId='mines-antipersonnel' LIMIT 1").fetchone()[0]
        for country in ('su', 'ru'):
            self.db.execute('INSERT OR IGNORE INTO card_countries VALUES (?,?)', (card, country))
        self.assert_all_menus()
        self.db.execute('UPDATE cards SET archived=1 WHERE id=?', (card,))
        self.assert_all_menus()

    def test_menu_counts_ignore_changes_to_favorites_and_reading(self):
        before = self.db.execute(query('menuCountryTotals')).fetchall()
        card = self.db.execute('SELECT id FROM cards LIMIT 1').fetchone()[0]
        self.db.execute('INSERT OR REPLACE INTO favorites VALUES (?,123)', (card,))
        self.db.execute('INSERT OR REPLACE INTO reading VALUES (?,0,0,123,147)', (card,))
        self.assertEqual(before, self.db.execute(query('menuCountryTotals')).fetchall())


if __name__ == '__main__':
    unittest.main()
