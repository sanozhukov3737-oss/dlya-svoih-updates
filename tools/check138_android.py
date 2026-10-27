"""Verify signed direct and bridge upgrades, then open models in the release APK."""
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
BASELINE_SHA='f0a67816b64c831259f54c1da10b010e50ef781ad9bb75010dab89be3715eebe'

def snapshot(name):
    state=ui.snapshot(name)
    with sqlite3.connect(ui.out/name/'databases/guide.db') as db:
        state['reading']=db.execute('select * from reading order by cardId').fetchall()
    return state

def install(path):
    result=ui.adb('install','-r','--no-streaming',path,timeout=420).decode()
    assert 'Success' in result,result

def assert_saved(before,after):
    for field in ['cards','favorites','reading','appearance','metadata','images']:
        assert before[field]==after[field],field

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--apks',type=Path,required=True);p.add_argument('--previous',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--api',type=int,required=True)
    a=p.parse_args();ui.out=a.out.resolve();ui.out.mkdir(parents=True,exist_ok=True)
    ui.tree=qa.hierarchy;ui.find=qa.find
    result={'api':a.api,'passed':False,'checks':{},'searchObservationUpperBoundsMs':{},'candidateSourceCommit':
        json.loads((a.apks/'build-result.json').read_text())['candidateSourceCommit']}
    try:
        assert hashlib.file_digest(a.previous.open('rb'),'sha256').hexdigest()==BASELINE_SHA
        assert int(ui.adb('shell','getprop','ro.build.version.sdk').decode().strip())==a.api
        for name in ['debug.apk','test.apk']:install(a.apks/name)
        classes='ru.dlyasvoih.app.RemoteAppContractTest'
        output=ui.adb('shell','am','instrument','-w','-r','-e','class',classes,
            'ru.dlyasvoih.app.test/androidx.test.runner.AndroidJUnitRunner',timeout=180).decode(errors='replace')
        (ui.out/'contract-tests.txt').write_text(output)
        assert 'OK (3 tests)' in output and 'FAILURES!!!' not in output,output
        ui.adb('uninstall','ru.dlyasvoih.app.test');ui.adb('uninstall',ui.PACKAGE)
        ui.adb('root',timeout=20);ui.adb('wait-for-device',timeout=30)
        for service in ['wifi','data']:ui.adb('shell','svc',service,'disable')
        ui.adb('shell','settings','put','global','airplane_mode_on','1')
        install(a.previous);qa.cold_start('baseline137')
        ui.appearance_dialog();ui.tap(ui.text('Тёмная'));ui.tap(ui.text('Готово'))
        ui.tap(qa.search('PMN2','ПМН-2',result));ui.text('Карточка')
        ui.tap(ui.description('В избранное'));ui.description('Убрать из избранного')
        before=snapshot('before')
        assert len(before['cards'])==1695 and before['favorites'] and before['reading']
        install(a.apks/'DLYA_SVOIH_v0.3.138_Update_Helper.apk');qa.cold_start('bridge142')
        assert_saved(before,snapshot('bridge'))
        assert 'versionCode=142' in ui.adb('shell','dumpsys','package',ui.PACKAGE).decode()
        install(a.apks/'DLYA_SVOIH_v0.3.138.apk');qa.cold_start('full143')
        assert_saved(before,snapshot('full'))
        result['checks']['bridgeChainPreservesData']=True
        # Recreate the original signed installation to test a direct update too.
        ui.adb('uninstall',ui.PACKAGE);install(a.previous);qa.cold_start('direct-baseline')
        ui.appearance_dialog();ui.tap(ui.text('Тёмная'));ui.tap(ui.text('Готово'))
        ui.tap(qa.search('PMN2','ПМН-2',result));ui.text('Карточка')
        ui.tap(ui.description('В избранное'));ui.description('Убрать из избранного')
        direct=snapshot('direct-before')
        install(a.apks/'DLYA_SVOIH_v0.3.138.apk');qa.cold_start('direct-full')
        assert_saved(direct,snapshot('direct-after'))
        result['checks']['directUpgradePreservesData']=True
        assert 'versionCode=143' in ui.adb('shell','dumpsys','package',ui.PACKAGE).decode()
        # The release WebView is exercised through the visible gallery search.
        ui.catalog_root();ui.tap(ui.description('Открыть меню'));ui.tap(ui.text('3D-модели · офлайн'))
        ui.text('615 из 615 моделей · офлайн');ui.capture('release-gallery')
        field=qa.find(lambda n:n.get('class')=='android.widget.EditText')
        ui.tap(field);ui.adb('shell','input','text','pmn-classic');ui.adb('shell','input','keyevent','4')
        item=qa.find(lambda n:'ПМН' in n.get('text','') and '3D' not in n.get('text',''))
        ui.tap(item)
        ui.text('Поворот — одним пальцем · Масштаб — двумя')
        deadline=time.monotonic()+45
        while time.monotonic()<deadline:
            texts=[n.get('text','') for n in qa.hierarchy().iter('node')]
            if not any('Открываем модель' in text for text in texts):break
            time.sleep(.3)
        assert not any('Не удалось' in text or 'недоступен' in text for text in texts),texts
        ui.capture('release-pmn')
        ui.adb('shell','input','swipe',180,500,550,530,'650');time.sleep(.5)
        ui.capture('release-pmn-rotated')
        result['checks']['releaseGallerySearchAndModel']=True
        crash=ui.adb('logcat','-d','-b','crash').decode(errors='replace')
        (ui.out/'crash.log').write_text(crash)
        assert 'FATAL EXCEPTION' not in crash and 'Fatal signal' not in crash,crash
        result['passed']=True
    finally:
        (ui.out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps(result,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
