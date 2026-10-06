"""Compile and execute production Java search/download logic on a host JDK."""
from pathlib import Path
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


if __name__ == '__main__':
    unittest.main()
