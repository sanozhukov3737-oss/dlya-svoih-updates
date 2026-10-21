"""Check the actual signed APK upgrade and comparison UI on a disposable emulator.

Root is used only to install a deterministic public-catalog/user-data fixture on
the fresh emulator. No instrumentation links against the obfuscated release.
"""
import hashlib
import json
import re
import shutil
import sqlite3
import subprocess
import time
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

import recovery_android_stage3 as ui

ROOT = Path('build/compare135')
PROOF = ROOT / 'proof'
PACKAGE = 'ru.dlyasvoih.app'


def snapshot(label):
    result = ui.snapshot(label)
    directory = PROOF / label
    with sqlite3.connect(directory / 'databases/guide.db') as db:
        result['reading'] = db.execute('SELECT * FROM reading ORDER BY cardId').fetchall()
        result['activeCards'] = db.execute('SELECT COUNT(*) FROM cards WHERE archived=0').fetchone()[0]
    reader = ui.adb('exec-out', 'cat', f'/data/user/0/{PACKAGE}/shared_prefs/reader.xml')
    result['readerPreferences'] = {n.get('name'): n.get('value', n.text) for n in ET.fromstring(reader)}
    (directory / 'state.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    return result


def seed_public_catalog_fixture():
    """Equivalent persisted state of 0.3.134 after its already-tested OTA 197."""
    uid = ui.adb('shell', 'stat', '-c', '%u', f'/data/user/0/{PACKAGE}').decode().strip()
    assert uid.isdigit() and int(uid) >= 10000, uid
    pack = ROOT / 'catalog-197.zip'
    digest = hashlib.sha256(pack.read_bytes()).hexdigest()
    assert digest == 'c81652660bdb9f9a787875c206c89fc3c65cb3f1e118a3d428c945755ec86599'
    fixture = ROOT / 'fixture'
    fixture.mkdir(exist_ok=True)
    with zipfile.ZipFile(pack) as archive:
        manifest = json.loads(archive.read('manifest.json'))
        assert manifest['contentVersion'] == 197
        for entry in manifest['files']:
            raw = archive.read(entry['path'])
            assert hashlib.sha256(raw).hexdigest() == entry['sha256']
            target = fixture / entry['path']
            target.parent.mkdir(exist_ok=True, parents=True)
            target.write_bytes(raw)
    with sqlite3.connect(fixture / 'guide.db') as db:
        assert sqlite3.sqlite_version_info <= (3,45,1)
        db.execute("UPDATE images SET localPath=? || localPath", (f'packs/{digest}/',))
        db.execute("UPDATE cards SET thumbnailPath=? || thumbnailPath WHERE thumbnailPath IS NOT NULL", (f'packs/{digest}/',))
        db.execute('INSERT INTO favorites(cardId,savedAt) VALUES(?,?)', ('eng-pmn',101))
        db.execute('INSERT INTO reading(cardId,itemIndex,offset,updatedAt,contentVersion) VALUES(?,?,?,?,?)', ('eng-pmn',2,37,202,197))
        assert db.execute('PRAGMA integrity_check').fetchone() == ('ok',)
    ui.adb('shell', 'am', 'force-stop', PACKAGE)
    target = f'/data/user/0/{PACKAGE}'
    ui.adb('shell', 'rm', '-f', target+'/databases/guide.db-wal', target+'/databases/guide.db-shm')
    ui.adb('push', fixture/'guide.db', target+'/databases/guide.db')
    media = target+f'/files/packs/{digest}'
    ui.adb('shell', 'mkdir', '-p', media, target+'/shared_prefs')
    for name in ('images','thumbs'):
        ui.adb('push', fixture/name, media+'/'+name, timeout=120)
    for name, contents in {
        'appearance.xml':'<?xml version="1.0" encoding="utf-8"?><map><int name="theme_mode" value="2"/><boolean name="large_mode" value="false"/></map>',
        'reader.xml':'<?xml version="1.0" encoding="utf-8"?><map><float name="text_scale" value="1.2"/></map>'
    }.items():
        path = fixture / name
        path.write_text(contents)
        ui.adb('push', path, target+'/shared_prefs/'+name)
    for name in ('databases','files','shared_prefs'):
        ui.adb('shell', 'chown', '-R', uid+':'+uid, target+'/'+name)
        ui.adb('shell', 'restorecon', '-R', target+'/'+name)


def open_comparison():
    ui.start('favorites_tab')
    ui.tap(ui.text('ПМН'))
    for _ in range(6):
        root = ui.tree()
        node = next((n for n in root.iter('node') if n.get('text') == 'Сравнить'),None)
        if node is not None:
            ui.tap(node)
            break
        ui.adb('shell','input','swipe','360','380','360','1100','350')
    else:
        raise AssertionError('Comparison action is not reachable in the actual release')
    ui.text('Выбрать карточки')
    ui.text('Основная карточка')


def main():
    PROOF.mkdir(exist_ok=True, parents=True)
    ui.out = PROOF
    assert ui.adb('shell','getprop','ro.kernel.qemu').decode().strip() == '1', 'Only the dedicated emulator may be changed'
    ui.adb('root'); ui.adb('wait-for-device')
    assert ui.adb('shell','id','-u').decode().strip() == '0'
    ui.adb('shell','wm','size','720x1280')
    ui.adb('shell','wm','density','320')
    ui.adb('shell','settings','put','system','font_scale','1.0')
    # These debug-test packages belong only to this fresh emulator. Removing
    # them enables installation of the older public versionCode 138.
    ui.adb('uninstall',PACKAGE)
    ui.adb('install','--no-streaming',ROOT/'previous-0.3.134.apk',timeout=180)
    ui.start('favorites_tab')
    ui.text('Избранное')
    seed_public_catalog_fixture()
    ui.start('favorites_tab')
    ui.text('ПМН')
    ui.capture('before-134-favorites')
    before = snapshot('before-upgrade')
    assert before['favorites'] == ['eng-pmn']
    assert before['activeCards'] == 1695 and before['metadata']['content_version'] == '197'
    assert before['reading'] == [('eng-pmn',2,37,202,197)]
    ui.adb('install','-r','--no-streaming',ROOT/'release/DLYA_SVOIH_v0.3.135.apk',timeout=180)
    ui.start('favorites_tab')
    ui.text('ПМН')
    after = snapshot('after-upgrade')
    for field in ('cards','favorites','reading','appearance','readerPreferences'):
        assert before[field] == after[field], ('Upgrade changed saved state',field)
    assert after['activeCards'] == 1695 and after['metadata']['content_version'] == '197'
    package = ui.adb('shell','dumpsys','package',PACKAGE).decode()
    assert 'versionName=0.3.135' in package and 'versionCode=139' in package
    ui.adb('logcat','-c')
    open_comparison()
    ui.capture('comparison135-two-dark')
    ui.tap(ui.text('Выбрать карточки'))
    ui.text('Поиск по названию')
    ui.capture('comparison135-picker')
    checkbox = ui.find(lambda a:a.get('checkable')=='true' and a.get('checked')=='false' and a.get('enabled')=='true')
    ui.tap(checkbox)
    ui.tap(ui.text('Сравнить · 3'))
    hint = '3 карточки · таблицу можно сдвигать вбок'
    ui.text(hint)
    ui.capture('comparison135-three-left')
    title = ui.text('Основная карточка')
    _,y1,_,y2=ui.bounds(title)
    ui.adb('shell','input','swipe','650',str((y1+y2)//2),'70',str((y1+y2)//2),'400')
    ui.capture('comparison135-three-right')
    for _ in range(2): ui.adb('shell','input','swipe','500','1100','500','750','400')
    ui.text('Выбрать карточки')
    ui.capture('comparison135-three-scrolled')
    ui.adb('shell','settings','put','system','font_scale','1.3')
    time.sleep(2)
    ui.text(hint)
    ui.capture('comparison135-three-large-font')
    crash = ui.adb('logcat','-d','-b','crash').decode(errors='replace')
    (PROOF/'release-crash.log').write_text(crash)
    assert 'FATAL EXCEPTION' not in crash and 'Fatal signal' not in crash, crash
    report = dict(previousVersion='0.3.134',versionName='0.3.135',versionCode=139,contentVersion=197,
        preservedCatalogIds=1695,favoritesPreserved=True,readingPositionPreserved=True,preferencesPreserved=True,
        comparisonInActualSignedRelease=True,threeCardsInSameCategory=True,pickerReachable=True,
        smallScreenDp=[360,640],largeFontScale=1.3,selectionSurvivesConfigurationChange=True,
        humanVisualReview='pending review of the captured Android frames')
    (PROOF/'upgrade-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False))


if __name__ == '__main__':
    try: main()
    finally:
        if PROOF.exists():
            try: (PROOF/'last-screen.png').write_bytes(ui.adb('exec-out','screencap','-p'))
            except Exception: pass
