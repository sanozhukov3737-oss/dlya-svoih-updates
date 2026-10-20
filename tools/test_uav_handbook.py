"""Check complete handbook coverage without merging similarly named models."""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class UavHandbookTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.coverage = json.loads((ROOT / 'research/uav-handbook-coverage-2026-10-19.json').read_text())
        catalog = json.loads((ROOT / 'content/catalog.json').read_text())
        cls.cards = {card['id']: card for card in catalog['cards']}

    def test_every_table_row_maps_to_a_card_and_exterior_policy(self):
        rows = self.coverage['observations']
        self.assertEqual(187, len(rows))
        self.assertEqual(set(range(2, 27)), {row['page'] for row in rows})
        self.assertEqual(187, len({(row['page'], row['slot']) for row in rows}))
        self.assertEqual(177, sum(row['status'] == 'new' for row in rows))
        self.assertEqual(8, len({row['mappedCardId'] for row in rows if row['status'] == 'existing'}))
        for row in rows:
            with self.subTest(page=row['page'], slot=row['slot']):
                card = self.cards[row['mappedCardId']]
                self.assertTrue(card['sources'])
                if row['imagePolicy'] == 'no-exterior-in-source':
                    self.assertEqual([], card['images'])
                else:
                    self.assertTrue(card['images'])
                if row['status'] == 'new':
                    self.assertEqual('source_only', card['contentStatus'])
                    self.assertIsNone(card['verifiedAt'])

    def test_same_names_and_variant_suffixes_remain_distinct(self):
        rows = {(row['page'], row['slot']): row for row in self.coverage['observations']}
        ukr = self.cards[rows[11, 6]['mappedCardId']]
        rus = self.cards['uavref-ofbch-25']
        self.assertEqual(['ua'], ukr['countries'])
        self.assertEqual(['ru'], rus['countries'])
        self.assertNotEqual(ukr['id'], rus['id'])
        self.assertNotEqual(rows[4, 2]['mappedCardId'], 'atlas-bp-bpla')
        self.assertEqual(rows[9, 8]['mappedCardId'], rows[10, 1]['mappedCardId'])
        self.assertEqual(rows[9, 8]['mappedCardId'], rows[10, 2]['mappedCardId'])
        self.assertNotEqual(rows[9, 4]['mappedCardId'], rows[10, 4]['mappedCardId'])
        self.assertNotEqual(rows[10, 3]['mappedCardId'], rows[11, 3]['mappedCardId'])
        self.assertNotEqual(rows[20, 4]['mappedCardId'], rows[20, 5]['mappedCardId'])
        self.assertNotEqual(rows[24, 1]['mappedCardId'], rows[24, 2]['mappedCardId'])
        self.assertEqual(9, len({rows[25, slot]['mappedCardId'] for slot in range(2, 11)}))


if __name__ == '__main__':
    unittest.main()
