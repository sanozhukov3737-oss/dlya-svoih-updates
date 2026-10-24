"""Exercise evidence capture with a simulated ADB; no physical-device claims."""
from contextlib import redirect_stdout
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest
from unittest.mock import patch
import zipfile

SCRIPT = Path(__file__).with_name('check_physical_android.py')
spec = importlib.util.spec_from_file_location('phone_capture_under_test', SCRIPT)
phone = importlib.util.module_from_spec(spec)
spec.loader.exec_module(phone)


class PhoneCaptureTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.out = self.root / 'results'
        self.adb = self.root / 'adb'
        self.log = self.root / 'commands.jsonl'
        self.adb.write_text('#!' + sys.executable + '\n' + textwrap.dedent('''\
            import json, os, sys
            from pathlib import Path
            command = sys.argv[1:]
            with open(os.environ['PHONE_FAKE_LOG'], 'a') as output:
                output.write(json.dumps(command) + '\\n')
            if command[:1] == ['-s']:
                command = command[2:]
            if command == ['devices', '-l']:
                print('List of devices attached')
                print('PHONE1 device model:TestPhone')
                if os.environ.get('PHONE_FAKE_SECOND'):
                    print('PHONE2 device model:SecondPhone')
            elif command == ['get-state']:
                print('device')
            elif command == ['shell', 'getprop', 'ro.kernel.qemu']:
                print(os.environ.get('PHONE_FAKE_EMULATOR', '0'))
            elif command == ['shell', 'dumpsys', 'package', 'ru.dlyasvoih.app']:
                print('versionName=' + os.environ.get('PHONE_FAKE_VERSION', '0.3.137'))
                print('versionCode=' + os.environ.get('PHONE_FAKE_CODE', '141') + ' minSdk=26')
            elif command == ['shell', 'dumpsys', 'connectivity']:
                print('Active default network: ' + os.environ.get('PHONE_FAKE_NETWORK', 'none'))
            elif command == ['shell', 'pm', 'path', 'ru.dlyasvoih.app']:
                print('package:/data/app/test/base.apk')
            elif command == ['exec-out', 'cat', '/data/app/test/base.apk']:
                sys.stdout.buffer.write(b'synthetic-installed-apk')
            elif command == ['shell', 'getprop']:
                print('[ro.product.model]: [TestPhone]')
            elif command[:3] == ['shell', 'uiautomator', 'dump']:
                print('UI hierarchy dumped')
            elif command == ['exec-out', 'cat', '/sdcard/dlya-svoih-phone-check.xml']:
                print('<hierarchy><node text="Synthetic screen"/></hierarchy>')
            elif command == ['exec-out', 'screencap', '-p']:
                sys.stdout.buffer.write(b'\\x89PNG\\r\\n\\x1a\\nsynthetic-image')
            elif command == ['logcat', '-d', '-b', 'crash']:
                pass
            else:
                print('Unexpected ADB command: ' + repr(command), file=sys.stderr)
                sys.exit(19)
            '''), encoding='utf-8')
        self.adb.chmod(0o700)
        self.environment = patch.dict(os.environ, {'PHONE_FAKE_LOG': str(self.log)})
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def valid_fixture_hash(self):
        return patch.dict(phone.VERSIONS, {'after': ('0.3.137', 141,
            hashlib.sha256(b'synthetic-installed-apk').hexdigest())})

    def test_auto_detection_and_private_wizard_archive(self):
        old = self.out / 'old-session'
        old.mkdir(parents=True)
        (old / 'private.txt').write_text('must not enter this session archive')
        self.assertEqual(phone.select_phone(str(self.adb)), 'PHONE1')
        self.assertEqual(phone.read_phase(str(self.adb), 'PHONE1')[0], 'after')
        with self.valid_fixture_hash(), patch('builtins.input', side_effect=['1', '', '0']), redirect_stdout(io.StringIO()):
            phone.wizard(str(self.adb), 'PHONE1', self.out)
        archive, = self.root.glob('DLYA_SVOIH_PHONE_RESULT_*.zip')
        with zipfile.ZipFile(archive) as bundle:
            self.assertFalse(any('old-session' in name for name in bundle.namelist()))
            metadata, = [name for name in bundle.namelist() if name.endswith('/evidence.json')]
            evidence = json.loads(bundle.read(metadata))
            self.assertEqual(evidence['phase'], 'after')
            self.assertEqual((evidence['versionName'], evidence['versionCode']), ('0.3.137', 141))
            self.assertTrue(evidence['physicalDevice'])
            self.assertEqual(evidence['manualFunctionalReview'], 'not-asserted-by-capture-script')
            self.assertNotIn('favoritesPreserved', evidence)
        calls = [json.loads(line) for line in self.log.read_text().splitlines()]
        self.assertFalse(any(call[:1] in (['install'], ['uninstall'], ['push'], ['root']) for call in calls))
        self.assertFalse(any('clear' in call or 'grant' in call for call in calls))

    def test_network_must_be_offline_before_evidence_is_written(self):
        with patch.dict(os.environ, {'PHONE_FAKE_NETWORK': '101'}), self.valid_fixture_hash():
            with self.assertRaisesRegex(ValueError, 'Офлайн-режим не подтверждён'):
                phone.capture(str(self.adb), 'PHONE1', 'after', 'gallery', self.out, True)
        self.assertFalse(self.out.exists())

    def test_emulator_is_rejected(self):
        with patch.dict(os.environ, {'PHONE_FAKE_EMULATOR': '1'}):
            with self.assertRaisesRegex(ValueError, 'Нужен физический телефон'):
                phone.select_phone(str(self.adb), 'PHONE1')
        self.assertFalse(self.out.exists())

    def test_two_phones_require_selection(self):
        with patch.dict(os.environ, {'PHONE_FAKE_SECOND': '1'}):
            with self.assertRaisesRegex(ValueError, 'несколько телефонов'):
                phone.select_phone(str(self.adb))

    def test_optimized_python_still_rejects_a_different_apk(self):
        result = subprocess.run([sys.executable, '-O', str(SCRIPT), '--adb', str(self.adb),
            '--label', 'favorites', '--out', str(self.out)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('APK на телефоне отличается', result.stderr)
        self.assertFalse(self.out.exists())

    def test_requested_wrong_phase_does_not_downgrade(self):
        with self.assertRaisesRegex(ValueError, 'Не удаляйте и не откатывайте'):
            phone.read_phase(str(self.adb), 'PHONE1', 'before')
        calls = [json.loads(line) for line in self.log.read_text().splitlines()]
        self.assertEqual(len(calls), 1)

    def test_published_versions_are_detected(self):
        for version, code, phase in [('0.3.136', '140', 'before'), ('0.3.137', '141', 'after')]:
            with self.subTest(version=version), patch.dict(os.environ,
                    {'PHONE_FAKE_VERSION': version, 'PHONE_FAKE_CODE': code}):
                self.assertEqual(phone.read_phase(str(self.adb), 'PHONE1')[0], phase)

    def test_old_version_and_wrong_version_code_are_rejected(self):
        for version, code in [('0.3.134', '138'), ('0.3.137', '140')]:
            with self.subTest(version=version, code=code), patch.dict(os.environ,
                    {'PHONE_FAKE_VERSION': version, 'PHONE_FAKE_CODE': code}):
                with self.assertRaisesRegex(ValueError, 'ничего не удаляйте'):
                    phone.read_phase(str(self.adb), 'PHONE1')
        self.assertFalse(self.out.exists())

    def test_capture_configuration_matches_published_releases_and_app(self):
        root = SCRIPT.parents[1]
        for phase, report in [('before', 'compatibility-136'), ('after', 'lazy-comparison-137')]:
            published = json.loads((root / 'research' / report / 'publication.json').read_text())
            self.assertTrue(published['releasePublished'])
            self.assertEqual(phone.VERSIONS[phase],
                (published['versionName'], published['versionCode'], published['apkSha256']))
        build = (root / 'app/build.gradle.kts').read_text()
        version, code, _ = phone.VERSIONS['after']
        self.assertIn('versionName = "' + version + '"', build)
        self.assertIn('versionCode = ' + str(code), build)


if __name__ == '__main__':
    unittest.main()
