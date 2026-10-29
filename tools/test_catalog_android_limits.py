"""Prevent a desktop-valid catalog from exceeding ContentUpdater text limits."""
import copy
import json
from pathlib import Path
import unittest
from build_catalog import validate


class AndroidCaptionCompatibilityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = json.loads((Path(__file__).resolve().parents[1] / 'content/catalog.json').read_text())

    def validate_caption(self, caption):
        data = copy.deepcopy(self.catalog)
        next(c for c in data['cards'] if c['images'])['images'][0]['caption'] = caption
        validate(data)

    def test_android_accepts_600_but_rejects_601_caption_units(self):
        self.validate_caption('а' * 600)
        with self.assertRaisesRegex(ValueError, 'caption'):
            self.validate_caption('а' * 601)

    def test_non_bmp_caption_counts_as_two_android_units(self):
        self.validate_caption('🟢' * 300)
        with self.assertRaisesRegex(ValueError, 'caption'):
            self.validate_caption('🟢' * 301)
