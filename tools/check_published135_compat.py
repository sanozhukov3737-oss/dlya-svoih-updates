#!/usr/bin/env python3
"""Read-only release QA on fresh Android 8/16 emulators; never rebuild the APK.

am start -W and Fully drawn logs are device timings. UI-observation times
include ADB/UIAutomator overhead and are upper bounds, not app benchmarks.
Frame statistics describe a short emulator sample, not physical-phone speed.
"""
import argparse
import hashlib
import json
import re
import sqlite3
import statistics
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import recovery_android_stage3 as ui

PACKAGE = ui.PACKAGE
APK_SHA = '068b71392f570ad768b59c391c10dbba8f9f90dce07d545b37bb545ffd71b3aa'


def announce(message):
    print(time.strftime('%H:%M:%S'), message, flush=True)


def hierarchy():
    """No hidden minute-long retries when a device or selector fails."""
    ui.adb('shell', 'uiautomator', 'dump', '/sdcard/compat135-ui.xml', timeout=15)
    raw = ui.adb('exec-out', 'cat', '/sdcard/compat135-ui.xml', timeout=10)
    (ui.out / 'last-ui.xml').write_bytes(raw)
    return ET.fromstring(raw)


def find(predicate, timeout=20):
    deadline = time.monotonic() + timeout
    while True:
        root = hierarchy()
        node = next((n for n in root.iter('node') if predicate(n.attrib)), None)
        if node is not None:
            return node
        if time.monotonic() >= deadline:
            raise AssertionError('UI element missing: ' + repr([
                n.get('text') or n.get('content-desc') for n in root.iter('node')
                if n.get('text') or n.get('content-desc')]))
        time.sleep(.2)


def cold_start(label):
    ui.adb('shell', 'am', 'force-stop', PACKAGE)
    ui.adb('logcat', '-c')
    raw = ui.adb('shell', 'am', 'start', '-W', '-n', PACKAGE + '/.MainActivity', timeout=60).decode()
    (ui.out / (label + '-am-start.txt')).write_text(raw)
    assert 'Status: ok' in raw and 'Error:' not in raw, raw
    ui.text('Инженерные боеприпасы')
    logs = ui.adb('logcat', '-d', '-v', 'brief').decode(errors='replace')
    relevant = [line for line in logs.splitlines() if PACKAGE in line and
                ('Displayed ' in line or 'Fully drawn ' in line)]
    (ui.out / (label + '-drawn.txt')).write_text('\n'.join(relevant) + '\n')
    timings = {key: int(value) for key, value in re.findall(
        r'^(ThisTime|TotalTime|WaitTime):\s*(\d+)', raw, re.MULTILINE)}
    assert timings.get('TotalTime', 0) > 0, raw
    return dict(**timings, drawnLog=relevant)


def search(query, title, report):
    ui.start('search_tab')
    for _ in range(6):
        root = hierarchy()
        field = next((n for n in root.iter('node') if n.get('class') == 'android.widget.EditText'), None)
        if field is not None:
            ui.tap(field)
            break
        back = next((n for n in root.iter('node') if n.get('content-desc') == 'Назад'), None)
        assert back is not None, 'Search has no field or visible back action'
        ui.tap(back)
    else:
        raise AssertionError('Search list could not be reached')
    ui.adb('shell', 'input', 'keyevent', 'KEYCODE_MOVE_END', *(['KEYCODE_DEL'] * 12))
    started = time.monotonic()
    ui.adb('shell', 'input', 'text', query)
    ui.adb('shell', 'input', 'keyevent', '4')
    result = ui.text(title)
    report['searchObservationUpperBoundsMs'][query] = round((time.monotonic() - started) * 1000)
    return result


def scroll_sample(label, report):
    before = [(n.get('text'), n.get('bounds')) for n in hierarchy().iter('node') if n.get('text')]
    ui.adb('shell', 'dumpsys', 'gfxinfo', PACKAGE, 'reset')
    for _ in range(4):
        ui.adb('shell', 'input', 'swipe', '420', '1040', '420', '470', '350')
        time.sleep(.2)
    after = [(n.get('text'), n.get('bounds')) for n in hierarchy().iter('node') if n.get('text')]
    assert before != after, 'Reader did not move after four visible gestures'
    raw = ui.adb('shell', 'dumpsys', 'gfxinfo', PACKAGE, 'framestats').decode(errors='replace')
    (ui.out / (label + '-gfxinfo.txt')).write_text(raw)
    total = re.search(r'Total frames rendered:\s*(\d+)', raw)
    janky = re.search(r'Janky frames:\s*(\d+)\s*\(([^)]+)\)', raw)
    percentiles = dict(re.findall(r'(50th|90th|95th|99th) percentile:\s*(\d+)ms', raw))
    durations = []
    header = None
    for line in raw.splitlines():
        if line.startswith('Flags,IntendedVsync,'):
            header = line.rstrip(',').split(',')
        elif header and re.match(r'^\d+,\d+,', line):
            values = line.rstrip(',').split(',')
            if len(values) != len(header):
                continue
            frame = dict(zip(header, map(int, values)))
            duration = frame.get('FrameCompleted', 0) - frame.get('IntendedVsync', 0)
            if frame['Flags'] == 0 and 0 < duration < 60_000_000_000:
                durations.append(duration / 1_000_000)
    assert total and int(total[1]) > 0 and durations, 'Android returned no frame evidence'
    report['scrollFrames'] = dict(totalFrames=int(total[1]),
        jankyFrames=int(janky[1]) if janky else None,
        jankyPercent=janky[2] if janky else None, percentileMs=percentiles,
        retainedFrameSample=len(durations), maxRetainedFrameMs=round(max(durations), 2),
        retainedFramesOver700ms=sum(t > 700 for t in durations))
    ui.capture(label)


def comparison(report):
    for _ in range(8):
        root = hierarchy()
        action = next((n for n in root.iter('node') if n.get('text') == 'Сравнить'), None)
        if action is not None:
            ui.tap(action)
            break
        ui.adb('shell', 'input', 'swipe', '420', '400', '420', '1050', '300')
    else:
        raise AssertionError('Comparison action is not reachable')
    ui.text('Выбрать карточки')
    ui.text('Основная карточка')
    ui.capture('comparison-two')
    ui.tap(ui.text('Выбрать карточки'))
    ui.text('Поиск по названию')
    option = find(lambda a: a.get('checkable') == 'true' and a.get('checked') == 'false'
                  and a.get('enabled') == 'true')
    ui.tap(option)
    ui.tap(ui.text('Сравнить · 3'))
    hint = '3 карточки · таблицу можно сдвигать вбок'
    ui.text(hint)
    ui.capture('comparison-three')
    title = ui.text('Основная карточка')
    _, y1, _, y2 = ui.bounds(title)
    ui.adb('shell', 'input', 'swipe', '650', (y1+y2)//2, '70', (y1+y2)//2, '400')
    ui.capture('comparison-three-panned')
    ui.adb('shell', 'settings', 'put', 'system', 'font_scale', '1.3')
    ui.text(hint)
    ui.capture('comparison-large-font')
    report['checks']['comparisonTwoAndThree'] = True
    report['checks']['selectionSurvivesFontConfiguration'] = True


def database_evidence(report):
    ui.adb('shell', 'am', 'force-stop', PACKAGE)
    dbdir = ui.out / 'databases'
    ui.adb('pull', '/data/user/0/' + PACKAGE + '/databases', dbdir, timeout=60)
    with sqlite3.connect('file:' + str((dbdir/'guide.db').resolve()) + '?mode=ro', uri=True) as db:
        assert db.execute('PRAGMA integrity_check').fetchone() == ('ok',)
        assert not db.execute('PRAGMA foreign_key_check').fetchall()
        cards = db.execute('SELECT count(*) FROM cards WHERE archived=0').fetchone()[0]
        version = db.execute("SELECT value FROM metadata WHERE key='content_version'").fetchone()[0]
        assert cards == 1695 and version == '197', (cards, version)
        assert db.execute('SELECT count(*) FROM favorites').fetchone()[0] == 1
        report['catalog'] = dict(contentVersion=int(version), activeCards=cards,
            images=db.execute('SELECT count(*) FROM images').fetchone()[0], integrity='ok', foreignKeys=0)
        report['checks']['favoritePersistedToDatabase'] = True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apk', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--expected-api', type=int, required=True)
    args = parser.parse_args()
    ui.out = args.out.resolve()
    ui.out.mkdir(parents=True, exist_ok=True)
    ui.tree = hierarchy
    ui.find = find
    report = dict(version='0.3.135', versionCode=139, apkSha256=APK_SHA, checks={},
        searchObservationUpperBoundsMs={}, passed=False, visualReview='pending',
        limitations=['Emulator timings are not physical-phone benchmarks.',
            'Search observations include ADB input, IME dismissal and UIAutomator dump latency.',
            'Scrolling is a short frame sample, not a full app performance profile.',
            'No APK/catalog update installation or 3D renderer test is performed in this stage.'])
    started = time.monotonic()
    try:
        assert hashlib.sha256(args.apk.read_bytes()).hexdigest() == APK_SHA
        assert ui.adb('shell', 'getprop', 'ro.kernel.qemu').decode().strip() == '1'
        assert not ui.adb('shell', 'pm', 'list', 'packages', PACKAGE).strip(), 'Fresh emulator required'
        api = int(ui.adb('shell', 'getprop', 'ro.build.version.sdk').decode().strip())
        assert api == args.expected_api
        report['api'] = api
        ui.adb('root')
        ui.adb('wait-for-device')
        assert ui.adb('shell', 'id', '-u').decode().strip() == '0'
        ui.adb('shell', 'wm', 'size', '720x1280')
        ui.adb('shell', 'wm', 'density', '320')
        ui.adb('shell', 'settings', 'put', 'system', 'font_scale', '1.0')
        for service in ('wifi', 'data'):
            ui.adb('shell', 'svc', service, 'disable')
        ui.adb('shell', 'settings', 'put', 'global', 'airplane_mode_on', '1')
        ui.adb('shell', 'am', 'broadcast', '-a', 'android.intent.action.AIRPLANE_MODE', '--ez', 'state', 'true')
        ui.offline('before-install')
        announce('Install exact public 0.3.135, offline')
        installed = ui.adb('install', '--no-streaming', args.apk, timeout=180).decode()
        assert 'Success' in installed, installed
        package = ui.adb('shell', 'dumpsys', 'package', PACKAGE).decode()
        (ui.out/'installed-package.txt').write_text(package)
        assert 'versionName=0.3.135' in package and 'versionCode=139' in package
        report['checks']['publicApkInstalledOffline'] = True
        report['firstRun'] = cold_start('first-run')
        ui.capture('home-offline')
        announce('Offline first launch passed; measure three subsequent cold starts')
        report['coldStarts'] = [cold_start('cold-' + str(i)) for i in range(1, 4)]
        report['coldStartMedianTotalMs'] = statistics.median(v['TotalTime'] for v in report['coldStarts'])
        ui.adb('logcat', '-c')
        announce('Search two names in the full catalog')
        search('TM46', 'ТМ-46', report)
        result = search('PMN2', 'ПМН-2', report)
        ui.capture('search-offline')
        ui.tap(result)
        ui.text('ПМН-2')
        ui.tap(ui.description('В избранное'))
        ui.description('Убрать из избранного')
        ui.capture('reader-offline')
        report['checks']['offlineSearchAndCard'] = True
        announce('Collect actual reader scroll frames')
        scroll_sample('reader-scrolled', report)
        announce('Comparison: two/three cards, pan and 1.3 font scale')
        comparison(report)
        ui.adb('shell', 'am', 'force-stop', PACKAGE)
        ui.start('favorites_tab')
        ui.text('ПМН-2')
        ui.capture('favorite-after-restart')
        report['checks']['favoriteSurvivesProcessRestart'] = True
        (ui.out/'meminfo.txt').write_bytes(ui.adb('shell', 'dumpsys', 'meminfo', PACKAGE))
        ui.offline('after-checks')
        database_evidence(report)
        crash = ui.adb('logcat', '-d', '-b', 'crash').decode(errors='replace')
        (ui.out/'crash.log').write_text(crash)
        assert 'FATAL EXCEPTION' not in crash and 'Fatal signal' not in crash, crash
        logs = ui.adb('logcat', '-d', '-b', 'main', '-b', 'system').decode(errors='replace')
        (ui.out/'device.log').write_text(logs)
        assert ('ANR in ' + PACKAGE) not in logs
        report['checks']['noCrashOrAnrObserved'] = True
        report['passed'] = True
        announce('All compatibility checks passed')
    except Exception as error:
        report['error'] = type(error).__name__ + ': ' + str(error)
        raise
    finally:
        report['durationSeconds'] = round(time.monotonic() - started, 2)
        (ui.out/'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        try:
            (ui.out/'last-screen.png').write_bytes(ui.adb('exec-out', 'screencap', '-p', timeout=10))
        except Exception:
            pass
        print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
