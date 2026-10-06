"""Compile and execute production Java search/download logic on a host JDK."""
from pathlib import Path
import base64
import json
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class JavaFeatureTests(unittest.TestCase):
    def test_apk_identity_version_and_signature_policy(self):
        java = shutil.which('java')
        if java is None:
            self.skipTest('JDK is not installed')
        sources = [ROOT / 'app/src/main/java/ru/dlyasvoih/app/data/update/ApkUpdatePolicy.java',
                   ROOT / 'test-common/HostApkChecks.java']
        with tempfile.TemporaryDirectory() as directory:
            compiled = subprocess.run([java, '-m', 'jdk.compiler/com.sun.tools.javac.Main', '-d', directory,
                *map(str, sources)], capture_output=True, text=True, timeout=30)
            self.assertEqual(0, compiled.returncode, compiled.stdout + compiled.stderr)
            checked = subprocess.run([java, '-cp', directory, 'ru.dlyasvoih.app.data.update.HostApkChecks'],
                capture_output=True, text=True, timeout=30)
            self.assertEqual(0, checked.returncode, checked.stdout + checked.stderr)
            self.assertIn('checks passed', checked.stdout)

    def test_reader_search_and_bounded_https_downloads(self):
        java = shutil.which('java')
        if java is None:
            self.skipTest('JDK is not installed')
        sources = [ROOT / 'app/src/main/java/ru/dlyasvoih/app/data/update/PackFiles.java',
                   ROOT / 'app/src/main/java/ru/dlyasvoih/app/data/update/RemoteFiles.java',
                   ROOT / 'app/src/main/java/ru/dlyasvoih/app/ui/ReaderIndex.java',
                   ROOT / 'test-common/HostFeatureChecks.java']
        with tempfile.TemporaryDirectory() as directory:
            compiled = subprocess.run([java, '-m', 'jdk.compiler/com.sun.tools.javac.Main', '-d', directory,
                *map(str, sources)], capture_output=True, text=True, timeout=30)
            self.assertEqual(0, compiled.returncode, compiled.stdout + compiled.stderr)
            checked = subprocess.run([java, '-cp', directory, 'ru.dlyasvoih.app.data.update.HostFeatureChecks'],
                capture_output=True, text=True, timeout=30)
            self.assertEqual(0, checked.returncode, checked.stdout + checked.stderr)
            self.assertIn('checks passed', checked.stdout)

    def test_articles_do_not_leak_notes_or_hide_variants(self):
        java = shutil.which('java')
        if java is None:
            self.skipTest('JDK is not installed')
        sources = [ROOT / 'app/src/main/java/ru/dlyasvoih/app/ui/content/ReferenceBodyParser.java',
                   ROOT / 'app/src/main/java/ru/dlyasvoih/app/ui/content/ReaderContent.java',
                   ROOT / 'test-common/HostReaderContentChecks.java']
        with tempfile.TemporaryDirectory() as directory:
            compiled = subprocess.run([java, '-m', 'jdk.compiler/com.sun.tools.javac.Main', '-d', directory,
                *map(str, sources)], capture_output=True, text=True, timeout=30)
            self.assertEqual(0, compiled.returncode, compiled.stdout + compiled.stderr)
            checked = subprocess.run([java, '-cp', directory, 'ru.dlyasvoih.app.ui.content.HostReaderContentChecks'],
                capture_output=True, text=True, timeout=30)
            self.assertEqual(0, checked.returncode, checked.stdout + checked.stderr)
            self.assertIn('checks passed', checked.stdout)

            # Compare actual Android reader projection against the DB builder's
            # article boundary for every model, including family and medical cards.
            cards = json.loads((ROOT / 'content/catalog.json').read_text())['cards']
            payload = Path(directory) / 'cards.txt'
            payload.write_text('\n'.join(base64.b64encode(c['body'].encode()).decode() for c in cards) + '\n')
            projected = subprocess.run([java, '-cp', directory, 'ru.dlyasvoih.app.ui.content.HostReaderContentChecks', str(payload)],
                capture_output=True, text=True, timeout=30)
            self.assertEqual(0, projected.returncode, projected.stderr)
            actual = [base64.b64decode(line).decode() for line in projected.stdout.splitlines()]
            self.assertEqual(len(cards), len(actual))
            for c, text in zip(cards, actual):
                self.assertEqual(c['body'].split('\n\n## Служебные сведения', 1)[0], text, c['id'])


if __name__ == '__main__':
    unittest.main()
