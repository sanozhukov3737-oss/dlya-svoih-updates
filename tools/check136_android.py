#!/usr/bin/env python3
"""Verify the exact signed 0.3.136 upgrade and IME regression on Android 8/16."""
import argparse
import hashlib
import json
import sqlite3
import statistics
import struct
import time
from pathlib import Path

import check_published135_compat as qa

ui = qa.ui
PACKAGE = qa.PACKAGE


def snapshot(label):
    state = ui.snapshot(label)
    with sqlite3.connect(ui.out / label / 'databases/guide.db') as db:
        state['reading'] = db.execute('SELECT * FROM reading ORDER BY cardId').fetchall()
    (ui.out / label / 'state.json').write_text(json.dumps(state, ensure_ascii=False, indent=2)+'\n')
    return state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('apk', 'previous', 'metadata', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--expected-api', type=int, required=True)
    args = parser.parse_args()
    ui.out = args.out.resolve()
    ui.out.mkdir(parents=True, exist_ok=True)
    ui.tree = qa.hierarchy
    ui.find = qa.find
    metadata = json.loads(args.metadata.read_text())
    report = dict(version='0.3.136', versionCode=140, apkSha256=metadata['apkSha256'],
        candidateSourceCommit=metadata['candidateSourceCommit'], checks={},
        searchObservationUpperBoundsMs={}, passed=False, visualReview='pending',
        limitations=['KVM/SwiftShader timings are emulator observations, not physical-phone benchmarks.',
            'Search upper bounds include ADB, IME dismissal and UIAutomator overhead.',
            'APK upgrade uses adb install -r; this is not an in-app download/installer test.',
            'Unchanged 3D renderer and catalog text are outside this regression test.'])
    started = time.monotonic()
    try:
        assert metadata['versionName']=='0.3.136' and metadata['versionCode']==140
        assert hashlib.sha256(args.apk.read_bytes()).hexdigest()==metadata['apkSha256']
        assert hashlib.sha256(args.previous.read_bytes()).hexdigest()==qa.APK_SHA
        assert ui.adb('shell', 'getprop', 'ro.kernel.qemu').decode().strip()=='1'
        assert not ui.adb('shell', 'pm', 'list', 'packages', PACKAGE).strip(), 'Fresh emulator required'
        api=int(ui.adb('shell', 'getprop', 'ro.build.version.sdk').decode().strip())
        assert api==args.expected_api
        report['api']=api
        ui.adb('root'); ui.adb('wait-for-device')
        assert ui.adb('shell', 'id', '-u').decode().strip()=='0'
        # Fresh API 26 Google images can show Gboard's first-use Contacts
        # permission dialog. Deny access on this disposable emulator; it is
        # unrelated to the app and no keyboard permission is ever granted.
        for permission in ('READ_CONTACTS','WRITE_CONTACTS'):
            ui.adb('shell','pm','revoke','com.google.android.inputmethod.latin',
                'android.permission.'+permission,check=False)
            ui.adb('shell','pm','set-permission-flags','com.google.android.inputmethod.latin',
                'android.permission.'+permission,'user-set','user-fixed',check=False)
        png=ui.adb('exec-out', 'screencap', '-p')
        assert png[:8]==b'\x89PNG\r\n\x1a\n' and struct.unpack('>II',png[16:24])==(720,1280), 'Native 720x1280 AVD required; no legacy wm scaling'
        for service in ('wifi', 'data'):
            ui.adb('shell', 'svc', service, 'disable')
        ui.adb('shell', 'settings', 'put', 'global', 'airplane_mode_on', '1')
        ui.adb('shell', 'am', 'broadcast', '-a', 'android.intent.action.AIRPLANE_MODE', '--ez', 'state', 'true')
        ui.offline('before-install')
        qa.announce('Install exact public 0.3.135 and prepare saved state through its UI')
        assert 'Success' in ui.adb('install','--no-streaming',args.previous,timeout=180).decode()
        report['previousFirstRun']=qa.cold_start('before-135-first-launch')
        ui.tap(qa.search('PMN2','ПМН-2',report))
        ui.text('Карточка')
        ui.tap(ui.description('В избранное'))
        ui.description('Убрать из избранного')
        ui.appearance_dialog()
        ui.tap(ui.text('Тёмная')); ui.tap(ui.text('Готово'))
        before=snapshot('before-upgrade')
        assert len(before['cards'])==1695 and len(before['favorites'])==1 and before['reading']
        assert before['appearance']['theme_mode']=='2'
        qa.announce('Upgrade to the signed release 0.3.136 without clearing any app data')
        assert 'Success' in ui.adb('install','-r','--no-streaming',args.apk,timeout=180).decode()
        report['firstMeasuredColdAfterUpgrade']=qa.cold_start('after-upgrade-first-launch')
        ui.capture('home-offline')
        after=snapshot('after-upgrade')
        for field in ('cards','favorites','reading','appearance'):
            assert before[field]==after[field], ('Saved state changed',field)
        package=ui.adb('shell','dumpsys','package',PACKAGE).decode()
        (ui.out/'installed-package.txt').write_text(package)
        assert 'versionName=0.3.136' in package and 'versionCode=140' in package
        report['upgrade']=dict(previous='0.3.135',previousApkSha256=qa.APK_SHA,
            idAndRowidCount=1695,idsPreserved=True,favoritesPreserved=True,
            readingPreserved=True,appearancePreserved=True,method='adb install -r')
        qa.announce('Measure three subsequent cold starts and search the full catalog offline')
        report['coldStarts']=[qa.cold_start('cold-'+str(i)) for i in range(1,4)]
        report['coldStartMedianTotalMs']=statistics.median(v['TotalTime'] for v in report['coldStarts'])
        qa.search('TM46','ТМ-46',report)
        result=qa.search('PMN2','ПМН-2',report)
        ui.capture('search-offline'); ui.tap(result); ui.text('Карточка')
        ui.description('Убрать из избранного'); ui.capture('reader-offline')
        report['checks']['offlineSearchAndCard']=True
        qa.scroll_sample('reader-scrolled',report)
        qa.announce('Apply comparison with the keyboard open, then check three cards and large font')
        qa.comparison(report,exercise_keyboard=True)
        ui.adb('shell','am','force-stop',PACKAGE); ui.start('favorites_tab'); ui.text('ПМН-2')
        ui.capture('favorite-after-restart')
        report['checks']['favoriteSurvivesProcessRestart']=True
        (ui.out/'meminfo.txt').write_bytes(ui.adb('shell','dumpsys','meminfo',PACKAGE))
        ui.offline('after-checks')
        qa.database_evidence(report)
        crash=ui.adb('logcat','-d','-b','crash').decode(errors='replace')
        (ui.out/'crash.log').write_text(crash)
        assert 'FATAL EXCEPTION' not in crash and 'Fatal signal' not in crash,crash
        logs=ui.adb('logcat','-d','-b','main','-b','system').decode(errors='replace')
        (ui.out/'device.log').write_text(logs)
        assert ('ANR in '+PACKAGE) not in logs
        report['checks']['noCrashOrAnrObserved']=True
        report['passed']=True
        qa.announce('Signed upgrade, saved state and IME regression passed')
    except Exception as error:
        report['error']=type(error).__name__+': '+str(error)
        raise
    finally:
        report['durationSeconds']=round(time.monotonic()-started,2)
        (ui.out/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        try:
            (ui.out/'last-screen.png').write_bytes(ui.adb('exec-out','screencap','-p',timeout=10))
        except Exception:
            pass
        print(json.dumps(report,ensure_ascii=False),flush=True)


if __name__=='__main__': main()
