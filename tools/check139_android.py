"""Verify the exact signed upgrade, optional pack lifecycle, and update notifications."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import time
import check_published135_compat as qa

ui=qa.ui

def install(path):
    result=ui.adb('install','-r','--no-streaming',path,timeout=420).decode()
    assert 'Success' in result,result

def snapshot(name):
    state=ui.snapshot(name)
    with sqlite3.connect(ui.out/name/'databases/guide.db') as db:
        state['reading']=db.execute('select * from reading order by cardId').fetchall()
    return state

def saved(before,after):
    for key in ['cards','images','favorites','reading','appearance','metadata']:assert before[key]==after[key],key

def cold(label):
    ui.adb('shell','am','force-stop',ui.PACKAGE)
    output=ui.adb('shell','am','start','-W','-n',ui.PACKAGE+'/.MainActivity',timeout=60).decode()
    (ui.out/(label+'-start.txt')).write_text(output)
    assert 'Status: ok' in output,output
    ui.description('Открыть меню')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--apks',type=Path,required=True);p.add_argument('--previous',type=Path,required=True)
    p.add_argument('--pack',type=Path);p.add_argument('--out',type=Path,required=True);p.add_argument('--api',type=int,required=True)
    a=p.parse_args();ui.out=a.out.resolve();ui.out.mkdir(parents=True,exist_ok=True);ui.tree=qa.hierarchy;ui.find=qa.find
    result={'passed':False,'api':a.api,'checks':{},'searchObservationUpperBoundsMs':{},
        'sourceCommit':json.loads((a.apks/'build-result.json').read_text())['sourceCommit'],
        'qaSourceCommit':os.environ.get('GITHUB_SHA'),
        'testApkSha256':hashlib.sha256((a.apks/'test.apk').read_bytes()).hexdigest()}
    try:
        with a.previous.open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()=='fa34fe2206a2c0be03dd3cf650be978385549099f9589cc7239fc3809ab60852'
        for attempt in range(4):
            ui.adb('root',check=False,timeout=30)
            ui.adb('wait-for-device',timeout=30)
            if ui.adb('shell','id','-u',check=False,timeout=30).decode().strip()=='0':break
            time.sleep(2)
        else:raise AssertionError('The dedicated emulator did not reconnect as root')
        assert int(ui.adb('shell','getprop','ro.build.version.sdk').decode().strip())==a.api
        for service in ['wifi','data']:ui.adb('shell','svc',service,'disable')
        install(a.previous);cold('baseline138')
        ui.appearance_dialog();ui.tap(ui.text('Тёмная'));ui.tap(ui.text('Готово'))
        ui.tap(qa.search('PMN2','ПМН-2',result));ui.text('Карточка');ui.tap(ui.description('В избранное'));ui.description('Убрать из избранного')
        before=snapshot('before');assert len(before['cards'])==1695 and before['images']==1595 and before['favorites'] and before['reading']
        install(a.apks/'DLYA_SVOIH_v0.3.139.apk');cold('release139')
        saved(before,snapshot('after-upgrade'));result['checks']['signedUpgrade143to144PreservesData']=True
        assert 'versionCode=144' in ui.adb('shell','dumpsys','package',ui.PACKAGE).decode()
        a.previous.unlink()  # disposable download on this fresh CI runner, already hash-verified above
        cold('release-small')
        ui.catalog_root();ui.tap(ui.description('Открыть меню'));ui.tap(ui.text('3D-модели · офлайн'))
        ui.text('Скачать 615 моделей');ui.capture('release-no-model-pack')
        result['checks']['releaseWorksWithoutModelPack']=True
        # Keep the same signed app data while switching to its debug build for native tests.
        install(a.apks/'debug.apk');install(a.apks/'test.apk')
        if a.api>=33:ui.adb('shell','pm','grant',ui.PACKAGE,'android.permission.POST_NOTIFICATIONS')
        # The release gallery created the app-owned external directory through Android.
        if a.pack:
            ui.adb('push',a.pack,'/data/media/0/Android/data/'+ui.PACKAGE+'/files/models3d/fixture.zip',timeout=360)
        for service in ['wifi','data']:ui.adb('shell','svc',service,'enable')
        output=ui.adb('shell','am','instrument','-w','-r','-e','class',
            'ru.dlyasvoih.app.ui.screens.OptionalFeatures139Test','-e','realModelDownload','true' if a.api>=33 else 'false',
            'ru.dlyasvoih.app.test/androidx.test.runner.AndroidJUnitRunner',timeout=2100).decode(errors='replace')
        (ui.out/'instrumentation.txt').write_text(output);print(output[-10000:],flush=True)
        subprocess_ok=re.search(r'OK \(2 tests\)',output) is not None and 'FAILURES!!!' not in output
        ui.adb('pull','/data/media/0/Android/data/'+ui.PACKAGE+'/files/features139',ui.out/'native',timeout=120)
        assert subprocess_ok,output[-14000:]
        native=ui.out/'native'
        for name in ['model-pack-result.json','notification-result.json']:
            report=json.loads((native/name).read_text());assert report['passed'];result[name]=report
        # Instrumentation is finished: exercise the actual PendingIntent with
        # the ordinary Android clock instead of Compose's controlled test clock.
        ui.adb('shell','input','keyevent','3')
        ui.adb('shell','cmd','statusbar','expand-notifications')
        ui.tap(qa.find(lambda n:'Доступно обновление 0.3.140' in n.get('text','')))
        ui.text('Обновления');ui.text('Уведомления об обновлениях')
        ui.capture('notification-opened-updates')
        report=result['notification-result.json'];report['tapOpensUpdates']=True
        (native/'notification-result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        result['checks']['optionalPackLifecycleAndNotifications']=True
        ui.adb('uninstall','ru.dlyasvoih.app.test')
        install(a.apks/'DLYA_SVOIH_v0.3.139.apk')
        for service in ['wifi','data']:ui.adb('shell','svc',service,'disable')
        cold('release-with-pack');saved(before,snapshot('after-pack-lifecycle'));cold('release-offline')
        ui.catalog_root();ui.tap(ui.description('Открыть меню'));ui.tap(ui.text('3D-модели · офлайн'))
        ui.text('Управление');ui.capture('release-pack-installed')
        field=qa.find(lambda n:n.get('class')=='android.widget.EditText');ui.tap(field)
        ui.adb('shell','input','text','pmn-classic');ui.adb('shell','input','keyevent','4')
        ui.tap(qa.find(lambda n:'ПМН' in n.get('text','') and '3D' not in n.get('text','')))
        ui.text('Поворот — одним пальцем · Масштаб — двумя');time.sleep(2);ui.capture('release-model-initial')
        ui.adb('shell','input','swipe',180,500,550,530,'650');time.sleep(1);ui.capture('release-model-rotated')
        result['checks']['optimizedReleaseReadsExternalPackOffline']=True
        if a.api>=33:
            ui.adb('shell','pm','revoke',ui.PACKAGE,'android.permission.POST_NOTIFICATIONS')
            cold('notifications-denied');ui.text('Включить уведомления');ui.capture('notification-permission-choice')
            ui.tap(ui.text('Включить уведомления'))
            allow=qa.find(lambda n:'permission_allow_button' in n.get('resource-id',''))
            ui.tap(allow);time.sleep(.5)
            granted=ui.adb('shell','dumpsys','package',ui.PACKAGE).decode()
            assert re.search(r'android.permission.POST_NOTIFICATIONS: granted=true',granted)
            result['checks']['notificationPermissionRequest']=True
        crash=ui.adb('logcat','-d','-b','crash').decode(errors='replace');(ui.out/'crash.log').write_text(crash)
        assert 'FATAL EXCEPTION' not in crash and 'Fatal signal' not in crash,crash
        result['passed']=True
    finally:
        if not result['passed']:
            try: ui.adb('pull','/data/media/0/Android/data/'+ui.PACKAGE+'/files/features139',ui.out/'native',timeout=45)
            except Exception: pass
            try: ui.capture('failure-ui')
            except Exception: pass
            try: (ui.out/'failure-crash.log').write_bytes(ui.adb('logcat','-d','-b','crash'))
            except Exception: pass
        (ui.out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
