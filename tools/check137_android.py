#!/usr/bin/env python3
"""One bounded regression run and sequential A/B swipe samples on a fresh emulator."""
import argparse
import hashlib
import json
import re
import sqlite3
import subprocess
import time
from pathlib import Path

import check_published135_compat as qa

ui = qa.ui
BASELINE_SHA = '0a22658eab2cc409eebf1c9d62cb1139b79cbb160e238ebc5102b8abc4566162'


def position():
    root = qa.hierarchy()
    button = next(n for n in root.iter('node') if n.get('content-desc') == 'Перейти к карточке')
    x1, y1, x2, y2 = ui.bounds(button)
    for node in root.iter('node'):
        match = re.fullmatch(r'(\d+)\s*/\s*(\d+)', node.get('text', ''))
        if match:
            a, b, c, d = ui.bounds(node)
            if x1 <= a < c <= x2 and y1 <= b < d <= y2:
                return int(match[1]), int(match[2])
    raise AssertionError('Visible reader counter is missing')


def swipe_samples(label):
    ui.catalog_root()
    ui.tap(ui.text('Инженерные боеприпасы'))
    ui.tap(ui.text('Противопехотные мины'))
    ui.tap(ui.text('Все страны'))
    ui.description('Следующая карточка')
    assert position() == (1, 194)
    ui.capture(label + '-reader-start')
    results = []
    for batch in range(3):
        ui.adb('shell', 'dumpsys', 'gfxinfo', ui.PACKAGE, 'reset')
        # Six next and six previous gestures; actual full reader pages, no
        # UIAutomator polling during the batch. Animations remain at the same
        # emulator settings for baseline and candidate.
        for forward in (True, False):
            for _ in range(6):
                a, b = (576, 144) if forward else (144, 576)
                ui.adb('shell', 'input', 'swipe', a, 700, b, 700, '350')
                time.sleep(.25)
            assert position()[0] == (7 if forward else 1)
        raw = ui.adb('shell', 'dumpsys', 'gfxinfo', ui.PACKAGE, 'framestats').decode(errors='replace')
        (ui.out / f'{label}-batch{batch+1}-gfxinfo.txt').write_text(raw)
        results.append(qa.frame_report(raw))
    ui.capture(label + '-reader-returned')
    (ui.out / (label + '-meminfo.txt')).write_bytes(ui.adb('shell', 'dumpsys', 'meminfo', ui.PACKAGE))
    return results


def snapshot(name):
    result = ui.snapshot(name)
    with sqlite3.connect(ui.out / name / 'databases/guide.db') as db:
        result['reading'] = db.execute('SELECT * FROM reading ORDER BY cardId').fetchall()
    (ui.out / name / 'state.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def instrument(apks):
    for name in ('debug.apk', 'test.apk'):
        assert 'Success' in ui.adb('install', '--no-streaming', apks / name, timeout=180).decode()
    classes = ','.join('ru.dlyasvoih.app.' + name for name in (
        'LazyComparisonTest', 'ui.screens.ComparisonSheetTest', 'ui.screens.CardReaderPagesTest'))
    output = ui.adb('shell', 'am', 'instrument', '-w', '-r', '-e', 'class', classes,
                    'ru.dlyasvoih.app.test/androidx.test.runner.AndroidJUnitRunner', timeout=360).decode(errors='replace')
    (ui.out / 'instrumentation.txt').write_text(output)
    for name in ('comparison-options-loading', 'comparison-options-error',
                 'comparison-options-retry-ready', 'comparison-options-empty', 'comparison-test-failure'):
        image = ui.adb('exec-out', 'run-as', ui.PACKAGE, 'cat', 'files/' + name + '.png', check=False)
        if image.startswith(b'\x89PNG'):
            (ui.out / (name + '.png')).write_bytes(image)
    match = re.search(r'OK \((\d+) tests?\)', output)
    assert match and int(match[1]) == 14 and 'FAILURES!!!' not in output, output[-12000:]
    ui.adb('uninstall', 'ru.dlyasvoih.app.test')
    ui.adb('uninstall', ui.PACKAGE)
    return int(match[1])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apks', type=Path, required=True)
    parser.add_argument('--previous', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--expected-api', type=int, required=True)
    args = parser.parse_args()
    ui.out = args.out.resolve(); ui.out.mkdir(parents=True, exist_ok=True)
    ui.tree = qa.hierarchy; ui.find = qa.find
    metadata = json.loads((args.apks / 'build-result.json').read_text())
    report = dict(versionName='0.3.137', versionCode=141, api=args.expected_api,
        apkSha256=metadata['apkSha256'], candidateSourceCommit=metadata['candidateSourceCommit'],
        checks={}, searchObservationUpperBoundsMs={}, passed=False,
        limitations=['KVM and software SwiftShader; no physical-phone result.',
            'Same emulator, baseline first then signed upgrade; order and runner load are not randomized.',
            'Three batches of 12 real horizontal reader swipes per APK, first and repeated passes mixed.',
            'gfxinfo describes frame timing, not elapsed time to ready text or first decoded image.',
            'Image decoding latency and memory-cache hit rate are not measured.',
            'ADB signed upgrade, not an in-app installer test.'])
    started = time.monotonic()
    try:
        assert hashlib.sha256(args.previous.read_bytes()).hexdigest() == BASELINE_SHA
        assert hashlib.sha256((args.apks / 'DLYA_SVOIH_v0.3.137.apk').read_bytes()).hexdigest() == metadata['apkSha256']
        assert ui.adb('shell', 'getprop', 'ro.kernel.qemu').decode().strip() == '1'
        assert int(ui.adb('shell', 'getprop', 'ro.build.version.sdk').decode().strip()) == args.expected_api
        assert not ui.adb('shell', 'pm', 'list', 'packages', ui.PACKAGE).strip()
        for permission in ('READ_CONTACTS', 'WRITE_CONTACTS'):
            ui.adb('shell', 'pm', 'revoke', 'com.google.android.inputmethod.latin', 'android.permission.' + permission, check=False)
            ui.adb('shell', 'pm', 'set-permission-flags', 'com.google.android.inputmethod.latin',
                   'android.permission.' + permission, 'user-set', 'user-fixed', check=False)
        qa.announce('Run 14 focused Android checks, including the actual candidates SQL subscription')
        report['androidTests'] = instrument(args.apks)
        ui.adb('root', timeout=15)
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            try:
                if ui.adb('shell', 'id', '-u', timeout=3).decode().strip() == '0':
                    break
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                pass
            time.sleep(.3)
        else:
            raise AssertionError('Emulator root transport unavailable after 20 seconds')
        for service in ('wifi', 'data'):
            ui.adb('shell', 'svc', service, 'disable')
        ui.adb('shell', 'settings', 'put', 'global', 'airplane_mode_on', '1')
        ui.adb('shell', 'am', 'broadcast', '-a', 'android.intent.action.AIRPLANE_MODE', '--ez', 'state', 'true')
        ui.offline('before-baseline')
        qa.announce('Measure public 0.3.136 on the actual book-reader path')
        assert 'Success' in ui.adb('install', '--no-streaming', args.previous, timeout=180).decode()
        qa.cold_start('baseline-launch')
        ui.appearance_dialog(); ui.tap(ui.text('Тёмная')); ui.tap(ui.text('Готово'))
        report['baselineSwipeFrames'] = swipe_samples('baseline136')
        ui.tap(qa.search('PMN2', 'ПМН-2', report)); ui.text('Карточка')
        ui.tap(ui.description('В избранное')); ui.description('Убрать из избранного')
        ui.catalog_root()
        before = snapshot('before-upgrade')
        assert len(before['cards']) == 1695 and len(before['favorites']) == 1 and before['reading']
        assert before['appearance']['theme_mode'] == '2'
        qa.announce('Install the exact signed candidate, preserving all saved state')
        assert 'Success' in ui.adb('install', '-r', '--no-streaming', args.apks / 'DLYA_SVOIH_v0.3.137.apk', timeout=180).decode()
        qa.cold_start('candidate-launch')
        after = snapshot('after-upgrade')
        for field in ('cards', 'favorites', 'reading', 'appearance'):
            assert before[field] == after[field], ('Saved state changed', field)
        report['checks']['signedUpgradeAndSavedState'] = True
        package = ui.adb('shell', 'dumpsys', 'package', ui.PACKAGE).decode()
        (ui.out / 'installed-package.txt').write_text(package)
        assert 'versionName=0.3.137' in package and 'versionCode=141' in package
        qa.cold_start('candidate-restart')
        report['candidateSwipeFrames'] = swipe_samples('candidate137')
        ui.tap(qa.search('PMN2', 'ПМН-2', report)); ui.text('Карточка')
        ui.description('Убрать из избранного')
        qa.comparison(report, exercise_keyboard=True)
        qa.database_evidence(report)
        crash = ui.adb('logcat', '-d', '-b', 'crash').decode(errors='replace')
        (ui.out / 'crash.log').write_text(crash)
        assert 'FATAL EXCEPTION' not in crash and 'Fatal signal' not in crash, crash
        ui.offline('after-candidate')
        report['checks']['noCrashObserved'] = True
        report['passed'] = True
        qa.announce('Focused tests, signed upgrade and paired swipe samples completed')
    except Exception as error:
        report['error'] = type(error).__name__ + ': ' + str(error)
        raise
    finally:
        report['durationSeconds'] = round(time.monotonic() - started, 2)
        (ui.out / 'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        try:
            (ui.out / 'last-screen.png').write_bytes(ui.adb('exec-out', 'screencap', '-p', timeout=10))
        except Exception:
            pass
        print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
