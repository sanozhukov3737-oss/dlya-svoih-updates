"""Check full PDF coverage and disambiguation of catalog-specific products."""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DemzCatalogTests(unittest.TestCase):
    def test_every_product_page_has_a_real_card_mapping(self):
        coverage = json.loads((ROOT / 'research/demz-catalog-coverage-2026-10-19.json').read_text())
        catalog = json.loads((ROOT / 'content/catalog.json').read_text())
        cards = {c['id']: c for c in catalog['cards']}
        products = {p['key']: p for p in coverage['products']}
        self.assertEqual(set(range(3, 89)), {o['page'] for o in coverage['observations']})
        self.assertEqual(set(range(1, 93)), set(coverage['productPages']) |
                         {r['page'] for r in coverage['nonProductPages']})
        self.assertEqual(91, len(products))
        for entry in coverage['observations']:
            with self.subTest(page=entry['page'], model=entry['title']):
                self.assertIn(entry['cardId'], cards)
                self.assertEqual(products[entry['productKey']]['mappedCardId'], entry['cardId'])
                self.assertTrue(cards[entry['cardId']]['images'])

    def test_components_and_suffix_variants_keep_separate_identities(self):
        catalog = json.loads((ROOT / 'content/catalog.json').read_text())
        cards = {c['id']: c for c in catalog['cards']}
        self.assertEqual('munition-components', cards['demzref-shell-hull-m795']['categoryId'])
        self.assertEqual('artillery', cards['artillery-m795']['categoryId'])
        for key in ('ns', 's', 'nk', 'k'):
            for index in (600, 800, 1200, 1600):
                self.assertIn('demzref-moa-viy-' + str(index) + '-' + key, cards)
        for cid in ('demzref-rgd5e', 'demzref-rgo-f1-d', 'demzref-mon50-2m', 'demzref-ozm72ms'):
            self.assertIn(cid, cards)


if __name__ == '__main__':
    unittest.main()
