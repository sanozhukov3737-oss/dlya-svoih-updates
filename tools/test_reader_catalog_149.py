"""Release invariants for the reader edit, including model and numeric scopes."""
from pathlib import Path
import hashlib
import json
import sqlite3
import unittest

ROOT = Path(__file__).resolve().parents[1]
CARDS = json.loads((ROOT / 'content/catalog.json').read_text())['cards']
BY_ID = {c['id']: c for c in CARDS}


def article(card):
    return card['body'].split('\n\n## Служебные сведения', 1)[0]


class ReaderCatalogTests(unittest.TestCase):
    def test_all_models_images_sources_and_classifications_keep_identity(self):
        baseline = json.loads((ROOT / 'tools/reader_149_baseline.json').read_text())
        self.assertEqual({row['id'] for row in baseline}, set(BY_ID))
        for row in baseline:
            c = BY_ID[row['id']]
            identity = {k:v for k,v in c.items() if k not in ('summary','body')}
            digest = hashlib.sha256(json.dumps(identity, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
            self.assertEqual(row['identity'], digest, c['id'])
            for value in row['measurements']:
                self.assertIn(value, article(c), c['id'] + ': ' + value)
            if row['medicalBody']:
                self.assertEqual(row['medicalBody'], hashlib.sha256(c['body'].encode()).hexdigest(), c['id'])

    def test_service_notes_are_not_in_articles_or_search(self):
        with sqlite3.connect(ROOT / 'app/src/main/assets/database/guide-v29.db') as db:
            searches = dict(db.execute('SELECT id, searchText FROM cards'))
        for c in CARDS:
            text = article(c)
            for marker in ('Сведения о наполнении:', 'Источник дополнения:', 'Уточнение справочных данных:',
                           '## Примечания к источнику', '## Статус проверки', 'Исходная строка:', 'Исходная формулировка:'):
                self.assertNotIn(marker, text, c['id'])
            self.assertNotIn('исходная формулировка:', searches[c['id']], c['id'])
            self.assertLessEqual(len(c['summary']), 600)

    def test_variant_and_measurement_scopes_remain_visible(self):
        tm = article(BY_ID['eng-tm-62m'])
        for value in ('315 мм', '85 мм', '11,12 кг', '9,5 кг', '320 × 128 мм', 'без взрывателя', 'со взрывателем'):
            self.assertIn(value, tm)
        tm_d = article(BY_ID['mine-audit-v25-su-tm-62d'])
        for value in ('11,3–13,0 кг', '6,5–10,3 кг', '7,6–11,1 кг', '5,8–7,4 кг', 'только в комплектации с МВ-62'):
            self.assertIn(value, tm_d)
        hp = article(BY_ID['eng-pdf-v7-023'])
        for value in ('HPD1:', 'HPD1A:', 'HPD2:', 'HPD3:', 'только HPD-2A2', 'оси в таблице не подписаны'):
            self.assertIn(value, hp)
        m795 = article(BY_ID['artillery-m795'])
        self.assertIn('вариант TNT', m795)
        self.assertIn('вариант IMX-101', m795)
        self.assertNotIn('Май 2022', m795)
        self.assertIn('со взрывателем', m795)


if __name__ == '__main__':
    unittest.main()
