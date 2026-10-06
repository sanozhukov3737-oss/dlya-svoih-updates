import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from build_app_feed import (apk_metadata, write_app_feed, validate_app_metadata,
                            signing_certificate_digest, INITIAL_GITHUB_APK, RECOVERED_PC_APK)


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

    def test_v31_sdk_range_output_is_used_for_apk_metadata(self):
        certificate = 'B' * 64
        output = (f'Signer (minSdkVersion=33, maxSdkVersion=2147483647) certificate SHA-256 digest: {certificate}\r\n'
                  f'Signer (minSdkVersion=26, maxSdkVersion=32) certificate SHA-256 digest: {certificate}\r\n'
                  f'Source Stamp Signer certificate SHA-256 digest: {"c" * 64}\r\n')
        def result(args, **kwargs):
            values = {'application-id': 'ru.dlyasvoih.app', 'version-code': '118', 'version-name': '0.3.114', 'min-sdk': '26'}
            return subprocess.CompletedProcess(args, 0, stdout=output if args[0] == 'apksigner' else values[args[2]])
        with patch('build_app_feed.subprocess.run', side_effect=result):
            self.assertEqual(self.metadata, apk_metadata(self.apk, 'apkanalyzer', 'apksigner'))

    def test_multiple_certificates_and_parallel_signers_are_rejected(self):
        outputs = [
            f'Signer (minSdkVersion=33, maxSdkVersion=2147483647) certificate SHA-256 digest: {"b" * 64}\n'
            f'Signer (minSdkVersion=26, maxSdkVersion=32) certificate SHA-256 digest: {"c" * 64}',
            f'Signer #1 certificate SHA-256 digest: {"b" * 64}\nSigner #2 certificate SHA-256 digest: {"c" * 64}',
            f'Signer #1 certificate SHA-256 digest: {"b" * 64}\nSigner #2 certificate SHA-256 digest: {"b" * 64}',
        ]
        for output in outputs:
            with self.subTest(output=output), self.assertRaisesRegex(ValueError, 'one verified APK signing certificate'):
                signing_certificate_digest(output)

    def test_source_stamp_public_key_and_invalid_digests_are_rejected(self):
        outputs = [
            f'Source Stamp Signer certificate SHA-256 digest: {"b" * 64}',
            f'Signer #1 public key SHA-256 digest: {"b" * 64}',
            f'Signer #1 certificate SHA-256 digest: {"b" * 63}',
            f'Signer #1 certificate SHA-256 digest: {"b" * 65}',
            '',
        ]
        for output in outputs:
            with self.subTest(output=output), self.assertRaisesRegex(ValueError, 'one verified APK signing certificate'):
                signing_certificate_digest(output)

    def test_development_sdk_range_label_is_supported(self):
        output = f'Signer (minSdkVersion=33 (dev release=true), maxSdkVersion=2147483647) certificate SHA-256 digest: {"b" * 64}'
        self.assertEqual('b' * 64, signing_certificate_digest(output))

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
            expected = 'Increase versionCode' if code <= 118 else 'existing signing key'
            with self.subTest(code=code, key=key), self.assertRaisesRegex(ValueError, expected):
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

    def recovery_fixture(self):
        self.previous.write_text(json.dumps(dict(self.catalog, app=dict(formatVersion=1, **INITIAL_GITHUB_APK))))
        self.metadata = {k: v for k, v in RECOVERED_PC_APK.items() if k != 'url'}

    def write_recovery(self, enabled=True):
        with patch('build_app_feed.apk_metadata', return_value=self.metadata):
            return write_app_feed(self.apk, self.previous, RECOVERED_PC_APK['url'], self.output,
                                  repair_initial_publication=enabled)

    def test_initial_recovery_is_disabled_by_default(self):
        self.recovery_fixture()
        with self.assertRaisesRegex(ValueError, 'existing signing key'):
            self.write_recovery(enabled=False)
        self.assertFalse(self.output.exists())

    def test_exact_initial_recovery_preserves_catalog(self):
        self.recovery_fixture()
        feed = self.write_recovery()
        self.assertEqual(self.catalog, {k: v for k, v in feed.items() if k != 'app'})
        self.assertEqual(RECOVERED_PC_APK['signerSha256'], feed['app']['signerSha256'])
        self.assertEqual(hashlib.sha256(self.apk.read_bytes()).hexdigest(), feed['app']['sha256'])

    def test_initial_recovery_rejects_changed_old_release_or_new_identity(self):
        variants = [('previous', k, v) for k, v in (
            ('versionCode', 118), ('versionName', '0.3.114'), ('minSdk', 27),
            ('signerSha256', 'c' * 64), ('sha256', 'c' * 64), ('bytes', 72921718),
            ('url', 'https://example.com/other.apk'))]
        variants += [('new', k, v) for k, v in (
            ('versionCode', 121), ('versionName', '0.3.117'), ('minSdk', 27),
            ('signerSha256', 'c' * 64))]
        for side, field, value in variants:
            with self.subTest(side=side, field=field):
                self.recovery_fixture()
                if side == 'previous':
                    feed = json.loads(self.previous.read_text())
                    feed['app'][field] = value
                    self.previous.write_text(json.dumps(feed))
                else:
                    self.metadata[field] = value
                with self.assertRaisesRegex(ValueError, 'existing signing key'):
                    self.write_recovery()
                self.assertFalse(self.output.exists())

    def test_later_key_change_remains_blocked_after_recovery(self):
        self.recovery_fixture()
        previous = self.write_recovery()
        self.previous.write_text(json.dumps(previous))
        self.output.unlink()
        self.metadata.update(versionCode=121, versionName='0.3.117', signerSha256='c' * 64)
        with self.assertRaisesRegex(ValueError, 'existing signing key'):
            self.write_recovery()
        self.assertFalse(self.output.exists())


if __name__ == '__main__':
    unittest.main()
