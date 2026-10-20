from pathlib import Path
import hashlib
import json
import tempfile
import unittest
import zipfile
from build_catalog import ROOT
from build_pack import make_pack
from build_update_feed import describe_pack, write_feed


class UpdateFeedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.pack = Path(cls.directory.name) / 'catalog.zip'
        make_pack(ROOT / 'content/catalog.json', cls.pack)

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def test_feed_describes_exact_zip_without_rebuilding_or_modifying_it(self):
        before = hashlib.sha256(self.pack.read_bytes()).hexdigest()
        output = Path(self.directory.name) / 'latest.json'
        result = write_feed(self.pack, 'https://example.com/catalog.zip', output, 'Исправлены карточки')
        self.assertEqual(before, hashlib.sha256(self.pack.read_bytes()).hexdigest())
        self.assertEqual(before, result['sha256'])
        self.assertEqual(self.pack.stat().st_size, result['bytes'])
        catalog = json.loads((ROOT / 'content/catalog.json').read_text(encoding='utf-8'))
        self.assertEqual(catalog['contentVersion'], result['contentVersion'])
        self.assertEqual(result, json.loads(output.read_text(encoding='utf-8')))

    def test_rejects_unencrypted_and_credential_urls(self):
        for url in ('http://example.com/catalog.zip', 'https://user:pass@example.com/catalog.zip',
                    'https://example.com/catalog.zip#fragment', 'file:///catalog.zip'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                describe_pack(self.pack, url)

    def test_catalog_update_preserves_published_apk_offer(self):
        previous = Path(self.directory.name) / 'previous.json'
        app = dict(formatVersion=1, versionCode=118, versionName='0.3.114', packageName='ru.dlyasvoih.app',
            minSdk=26, url='https://example.com/app-118.apk', bytes=100, sha256='a' * 64,
            signerSha256='b' * 64, changes='Приложение')
        feed = describe_pack(self.pack, 'https://example.com/catalog-147.zip')
        feed['app'] = app
        previous.write_text(json.dumps(feed))
        output = Path(self.directory.name) / 'new-feed.json'
        result = write_feed(self.pack, 'https://example.com/catalog-next.zip', output, previous_feed=previous)
        self.assertEqual(app, result['app'])
        self.assertEqual(app, json.loads(output.read_text())['app'])

    def test_rejects_package_with_mismatched_declared_version(self):
        broken = Path(self.directory.name) / 'wrong-version.zip'
        with zipfile.ZipFile(self.pack) as source, zipfile.ZipFile(broken, 'w', compression=zipfile.ZIP_DEFLATED) as target:
            for info in source.infolist():
                payload = source.read(info.filename)
                if info.filename == 'manifest.json':
                    manifest = json.loads(payload)
                    manifest['contentVersion'] += 1
                    payload = json.dumps(manifest).encode()
                target.writestr(info.filename, payload)
        with self.assertRaisesRegex(ValueError, 'versions differ'):
            describe_pack(broken, 'https://example.com/catalog.zip')

    def test_rejects_changed_file_inside_package(self):
        broken = Path(self.directory.name) / 'changed-file.zip'
        with zipfile.ZipFile(self.pack) as source, zipfile.ZipFile(broken, 'w', compression=zipfile.ZIP_DEFLATED) as target:
            for info in source.infolist():
                payload = source.read(info.filename)
                if info.filename == 'guide.db':
                    payload = bytes([payload[0] ^ 1]) + payload[1:]
                target.writestr(info.filename, payload)
        with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
            describe_pack(broken, 'https://example.com/catalog.zip')


if __name__ == '__main__':
    unittest.main()
