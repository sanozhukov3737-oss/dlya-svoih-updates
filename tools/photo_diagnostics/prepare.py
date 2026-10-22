#!/usr/bin/env python3
"""Add timing observers only in an isolated, unpublished debug build."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]
SOURCES = {
    'app/src/main/java/ru/dlyasvoih/app/GuideApplication.kt': (
        '.diskCache(null)',
        '.diskCache(null)\n        .eventListenerFactory { ru.dlyasvoih.app.diagnostics.PhotoProbe.listener() }'),
    'app/src/main/java/ru/dlyasvoih/app/ui/screens/Components.kt': (
        'onError = { failed = true }, modifier = Modifier.fillMaxSize())',
        'transform = ru.dlyasvoih.app.diagnostics.PhotoProbe::transform,\n'
        '                onState = { if (it is coil3.compose.AsyncImagePainter.State.Error) failed = true }, modifier = Modifier.fillMaxSize())'),
    'app/src/main/java/ru/dlyasvoih/app/ui/screens/CardReaderScreen.kt': (
        'CardReaderPages(current.ids, vm.initialId, vm::rememberCard, jump)',
        'CardReaderPages(current.ids, vm.initialId, { id -> ru.dlyasvoih.app.diagnostics.PhotoProbe.settled(id); vm.rememberCard(id) }, jump)'),
    'app/build.gradle.kts': (
        'buildTypes {',
        'buildTypes {\n        getByName("debug") { applicationIdSuffix = ".photodiag"; versionNameSuffix = "-photo-diagnostic" }'),
}


def main():
    result = {'baseAppSource': '510727a0107b8c9a3be881fb5e871d6b78a253bd',
              'sourceCommit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
              'kind': 'unpublished debug diagnostics', 'patches': {}}
    for name, (before, after) in SOURCES.items():
        path = ROOT / name
        source = path.read_text()
        original = subprocess.check_output(['git', 'show', result['baseAppSource'] + ':' + name], cwd=ROOT)
        assert source.encode() == original, 'Production source changed: ' + name
        assert source.count(before) == 1, name
        patched = source.replace(before, after)
        path.write_text(patched)
        result['patches'][name] = {'beforeSha256': hashlib.sha256(original).hexdigest(),
                                 'afterSha256': hashlib.sha256(patched.encode()).hexdigest()}
    for filename, destination in (
        ('PhotoProbe.kt', 'app/src/debug/java/ru/dlyasvoih/app/diagnostics/PhotoProbe.kt'),
        ('PhotoLoadDiagnosticsTest.kt', 'app/src/androidTest/java/ru/dlyasvoih/app/ui/screens/PhotoLoadDiagnosticsTest.kt'),
    ):
        target = ROOT / destination
        assert not target.exists(), destination
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(Path(__file__).parent / filename, target)
    output = ROOT / 'build/photo-diagnostics/apks'
    output.mkdir(parents=True, exist_ok=True)
    (output / 'source-manifest.json').write_text(json.dumps(result, indent=2) + '\n')
    print('Diagnostic observers added to disposable checkout; production image settings retained')


if __name__ == '__main__':
    main()
