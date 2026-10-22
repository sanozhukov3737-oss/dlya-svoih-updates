#!/usr/bin/env python3
"""Run only the photo diagnostics on the fresh emulator owned by the outer runner."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

PACKAGE = 'ru.dlyasvoih.app.photodiag'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apks', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--expected-api', type=int, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    serial = os.environ['ANDROID_SERIAL']
    def adb(*argv, timeout=30, check=True, binary=False):
        return subprocess.run(['adb', '-s', serial, *argv], timeout=timeout, check=check,
                              capture_output=True, text=not binary)
    api = int(adb('shell', 'getprop', 'ro.build.version.sdk').stdout.strip())
    assert api == args.expected_api
    manifest = json.loads((args.apks / 'build-result.json').read_text())
    for name in ('debug.apk', 'test.apk'):
        assert hashlib.sha256((args.apks/name).read_bytes()).hexdigest() == manifest['apks'][name]['sha256']
        adb('install', '-r', '-t', str(args.apks/name), timeout=180)
    clear = adb('logcat', '-b', 'main', '-b', 'system', '-b', 'crash', '-c', check=False)
    (args.out/'log-clear.json').write_text(json.dumps({'returncode': clear.returncode,
        'stdout': clear.stdout, 'stderr': clear.stderr}, indent=2)+'\n')
    adb('shell', 'settings', 'put', 'system', 'font_scale', '1.0')
    adb('shell', 'svc', 'wifi', 'disable')
    adb('shell', 'svc', 'data', 'disable')
    for _ in range(20):
        connectivity = adb('shell', 'dumpsys', 'connectivity').stdout
        if 'Active default network: none' in connectivity or 'Active default network: null' in connectivity:
            break
        time.sleep(0.5)
    else:
        raise AssertionError('Emulator default network did not disconnect')
    (args.out/'connectivity.txt').write_text(connectivity)
    result = adb('shell', 'am', 'instrument', '-w', '-r', '-e', 'class',
                 'ru.dlyasvoih.app.ui.screens.PhotoLoadDiagnosticsTest', '-e', 'sourceCommit',
                 manifest['sourceCommit'], PACKAGE+'.test/androidx.test.runner.AndroidJUnitRunner', timeout=600, check=False)
    (args.out/'instrumentation.txt').write_text(result.stdout+'\n'+result.stderr)
    listing = adb('shell', 'run-as', PACKAGE, 'ls', 'files/photo-diagnostics', check=False)
    for name in listing.stdout.splitlines():
        if name == 'raw.json' or name in ('first-open.png', 'forward-end.png', 'returned.png'):
            content = adb('exec-out', 'run-as', PACKAGE, 'cat', 'files/photo-diagnostics/'+name, binary=True).stdout
            (args.out/name).write_bytes(content)
    (args.out/'crash.txt').write_text(adb('logcat', '-b', 'crash', '-d').stdout)
    (args.out/'device-logcat.txt').write_text(adb('logcat', '-d', '-v', 'threadtime').stdout)
    (args.out/'meminfo.txt').write_text(adb('shell', 'dumpsys', 'meminfo', PACKAGE).stdout)
    assert result.returncode == 0 and 'OK (1 test)' in result.stdout, 'Photo diagnostics instrumentation failed'
    raw = json.loads((args.out/'raw.json').read_text())
    assert raw['passed'] is True and raw['sdk'] == api and raw['packageName'] == PACKAGE
    assert len(raw['observations']) == 105
    assert 'FATAL EXCEPTION' not in (args.out/'crash.txt').read_text()
    assert not any(e['kind'] == 'requestError' for e in raw['events'])
    assert all(e.get('source') != 'NETWORK' for e in raw['events'])
    (args.out/'verification.json').write_text(json.dumps({'passed': True, 'api': api,
        'sourceCommit': manifest['sourceCommit'], 'harnessCommit': os.environ.get('GITHUB_SHA'),
        'productionApk': False, 'observations': 105,
        'limits': ['debug source build with timing observers', 'emulator, not physical phone',
                   'firstDraw records CPU painter draw, not display presentation',
                   'cache cleared, operating-system file cache not cleared']}, indent=2)+'\n')
    print('105 page observations complete, without image errors or network loads')


if __name__ == '__main__':
    main()
