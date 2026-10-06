import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from build_app_feed import apk_metadata, write_app_feed, validate_app_metadata


class AppFeedTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.apk = self.root / 'app.apk'
        with zipfile.ZipFile(self.apk, 'w') as z:
            z.writestr('AndroidManifest.xml', b'fixture')
        self.catalog = dict(formatVersion=1, contentVersion=147, url='https://example.com/catalog-147.zip',
                            bytes=100, sha256='a' * 64, changes='Каталог', minAppCode=116)
        self.previous = self.root / 'before.json'
        self.previous.write_text(json.dumps(self.catalog))
        self.output = self.root / 'latest.json'
        self.metadata = dict(packageName='ru.dlyasvoih.app', versionCode=118, versionName='0.3.114', minSdk=26, signerSha256='b' * 64)

    def write(self):
        with patch('build_app_feed.apk_metadata', return_value=self.metadata):
            return write_app_feed(self.apk, self.previous, 'https://example.com/app-118.apk', self.output, 'Интерфейс')

    def test_apk_feed_preserves_catalog_and_hashes_exact_apk(self):
        before = self.apk.read_bytes()
        feed = self.write()
        self.assertEqual(self.catalog, {k: v for k, v in feed.items() if k != 'app'})
        self.assertEqual(hashlib.sha256(before).hexdigest(), feed['app']['sha256'])
        self.assertEqual(len(before), feed['app']['bytes'])
        self.assertEqual(before, self.apk.read_bytes())
        self.assertEqual(feed, json.loads(self.output.read_text()))

    def test_apk_signing_tool_failure_stops_publication(self):
        with patch('build_app_feed.subprocess.run', side_effect=subprocess.CalledProcessError(1, 'apksigner')):
            with self.assertRaisesRegex(ValueError, 'validation failed'):
                apk_metadata(self.apk, 'apkanalyzer', 'apksigner')
        self.assertFalse(self.output.exists())

    def test_android_tool_metadata_is_used(self):
        def result(args, **kwargs):
            values = {'application-id': 'ru.dlyasvoih.app', 'version-code': '118', 'version-name': '0.3.114', 'min-sdk': '26'}
            output = 'Signer #1 certificate SHA-256 digest: ' + 'b' * 64 if args[0] == 'apksigner' else values[args[2]]
            return subprocess.CompletedProcess(args, 0, stdout=output)
        with patch('build_app_feed.subprocess.run', side_effect=result):
            self.assertEqual(self.metadata, apk_metadata(self.apk, 'apkanalyzer', 'apksigner'))

    def test_wrong_package_is_rejected_without_output(self):
        self.metadata['packageName'] = 'other.app'
        with self.assertRaisesRegex(ValueError, 'Wrong APK package'):
            self.write()
        self.assertFalse(self.output.exists())

    def test_same_or_lower_version_and_changed_key_are_rejected(self):
        previous = self.write()
        self.previous.write_text(json.dumps(previous))
        self.output.unlink()
        for code, key in ((118, 'b'), (117, 'b'), (119, 'c')):
            self.metadata.update(versionCode=code, signerSha256=key * 64)
            with self.subTest(code=code, key=key), self.assertRaisesRegex(ValueError, 'existing signing key'):
                self.write()
        self.assertFalse(self.output.exists())

    def test_invalid_metadata_is_rejected(self):
        valid = self.write()['app']
        for key, value in (('versionCode', True), ('versionCode', 1.5), ('bytes', 0), ('minSdk', 25),
                           ('url', 'http://example.com/a.apk'), ('signerSha256', 'oops')):
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_app_metadata(dict(valid, **{key: value}))

    def test_apk_cannot_be_overwritten_by_feed(self):
        with self.assertRaisesRegex(ValueError, 'overwrite'):
            write_app_feed(self.apk, self.previous, 'https://example.com/a.apk', self.apk)


if __name__ == '__main__':
    unittest.main()
