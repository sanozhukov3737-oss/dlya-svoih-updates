#!/usr/bin/env python3
"""Exercise the actual signed APK upgrade on a fresh dedicated Android emulator."""
import argparse
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
import traceback
import xml.etree.ElementTree as ET
from pathlib import Path

PACKAGE = 'ru.dlyasvoih.app'
SIGNED_SHA = '300b77deaee3348e05a0135bf0079414c07dc2e15a7dcfd9b1239a8cef99298f'
OLD_SHA = '8cff50f9d76dbeec261ca928603277bdf540d0d0b42913bde919a82ce8d5d49f'
out = None


def run(*command, timeout=120, check=True):
    return subprocess.run(list(map(str, command)), capture_output=True, timeout=timeout, check=check)


def adb(*args, **options):
    return run('adb', *args, **options).stdout


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def tree():
    for _ in range(4):
        adb('shell', 'uiautomator', 'dump', '/sdcard/recovery134-ui.xml', timeout=35)
        raw = adb('exec-out', 'cat', '/sdcard/recovery134-ui.xml')
        try:
            root=ET.fromstring(raw)
        except ET.ParseError:
            (out/'last-invalid-ui-dump.txt').write_bytes(raw)
            time.sleep(.5)
            continue
        (out / 'last-ui.xml').write_bytes(raw)
        return root
    raise AssertionError('Android UIAutomator did not return an XML hierarchy')


def find(predicate, timeout=40):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        root = tree()
        for node in root.iter('node'):
            if predicate(node.attrib):
                return node
        time.sleep(.4)
    raise AssertionError('UI element missing: ' + repr([
        n.get('text') or n.get('content-desc') for n in root.iter('node')
        if n.get('text') or n.get('content-desc')]))


def bounds(node):
    return tuple(map(int, re.findall(r'\d+', node.get('bounds'))))


def tap(node):
    x1, y1, x2, y2 = bounds(node)
    adb('shell', 'input', 'tap', (x1+x2)//2, (y1+y2)//2)


def text(value):
    return find(lambda a: a.get('text') == value)


def description(value):
    return find(lambda a: a.get('content-desc') == value)


def capture(name):
    (out / (name+'.xml')).write_bytes(ET.tostring(tree(), encoding='utf-8'))
    (out / (name+'.png')).write_bytes(adb('exec-out', 'screencap', '-p'))


def start(route='catalog'):
    adb('shell', 'am', 'start', '-W', '--activity-single-top', '-n', PACKAGE+'/.MainActivity', '--es', 'shortcut_route', route)


def search(query, title):
    start('search_tab')
    # Launcher shortcuts restore a tab's saved reader stack. Navigate visibly
    # back to its list instead of assuming that the shortcut clears that stack.
    for _ in range(8):
        root = tree()
        field = next((n for n in root.iter('node') if n.get('class') == 'android.widget.EditText'), None)
        if field is not None:
            tap(field)
            break
        back = next((n for n in root.iter('node') if n.get('content-desc') == 'Назад'), None)
        assert back is not None, 'Search tab has no visible field or back navigation'
        tap(back)
    else:
        raise AssertionError('Search tab list could not be reached')
    adb('shell', 'input', 'keyevent', 'KEYCODE_MOVE_END', *(['KEYCODE_DEL'] * 50))
    adb('shell', 'input', 'text', query)
    adb('shell', 'input', 'keyevent', '4')
    return text(title)


def offline(label):
    raw = adb('shell', 'dumpsys', 'connectivity').decode(errors='replace')
    (out / (label+'-connectivity.txt')).write_text(raw)
    match = re.search(r'Active default network:\s*(\S+)', raw)
    assert match and match[1].lower() in ('none', 'null', '-1'), 'Android still has a default network'


def snapshot(label):
    adb('shell', 'am', 'force-stop', PACKAGE)
    dest = out / label
    dest.mkdir(exist_ok=True)
    adb('pull', '/data/user/0/'+PACKAGE+'/databases', dest/'databases')
    prefs_raw = adb('exec-out', 'cat', '/data/user/0/'+PACKAGE+'/shared_prefs/appearance.xml')
    (dest / 'appearance.xml').write_bytes(prefs_raw)
    prefs = {n.get('name'): n.get('value', n.text) for n in ET.fromstring(prefs_raw)}
    db = sqlite3.connect(dest/'databases/guide.db')
    try:
        assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        assert not db.execute('PRAGMA foreign_key_check').fetchall()
        result = {'favorites': sorted(r[0] for r in db.execute('SELECT cardId FROM favorites')),
                  'cards': dict(db.execute('SELECT id,rowid FROM cards')),
                  'images': db.execute('SELECT count(*) FROM images').fetchone()[0],
                  'metadata': dict(db.execute('SELECT key,value FROM metadata')), 'appearance': prefs}
    finally:
        db.close()
    (dest/'state.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    return result


def catalog_root():
    start('catalog')
    tap(text('Каталог'))
    for _ in range(8):
        root=tree()
        if any(n.get('content-desc')=='Открыть меню' for n in root.iter('node')):
            return
        back=next((n for n in root.iter('node') if n.get('content-desc')=='Назад'),None)
        assert back is not None,'Catalog root has no visible back navigation'
        tap(back)
    raise AssertionError('Catalog root could not be reached')


def appearance_dialog():
    catalog_root()
    tap(description('Открыть меню'))
    tap(text('Тема и размер текста'))
    text('Вид приложения')


def verify_photo_and_navigation(report):
    # Two different photographs, native gallery zoom and reset, all offline.
    tap(search('PMN2', 'ПМН-2'))
    # Coil's Compose image exposes its actual caption, not an ImageView class.
    hero = find(lambda a: a.get('content-desc','').startswith('Сравнительный наружный вид:'))
    tap(hero)
    text('Изображения')
    description('Увеличить изображение')
    time.sleep(1)
    capture('gallery-photo-initial')
    tap(description('Увеличить изображение'))
    text('150%')
    capture('gallery-photo-zoomed')
    tap(description('Сбросить масштаб'))
    text('100%')
    tap(description('Изображение 2'))
    find(lambda a: a.get('text','').startswith('2 / 2'))
    capture('gallery-photo-second')
    from PIL import Image, ImageChops
    initial = Image.open(out/'gallery-photo-initial.png').convert('RGB')
    zoomed = Image.open(out/'gallery-photo-zoomed.png').convert('RGB')
    second = Image.open(out/'gallery-photo-second.png').convert('RGB')
    w,h = initial.size
    region=(int(w*.15),int(h*.25),int(w*.85),int(h*.65))
    assert len(set(initial.crop(region).getdata())) > 100, 'Photo did not produce visible pixels'
    assert ImageChops.difference(initial,zoomed).crop(region).getbbox(), 'Zoom did not change photo pixels'
    assert ImageChops.difference(initial,second).crop(region).getbbox(), 'Second photograph did not change'
    report['galleryZoomAndSecondPhoto']=True
    (out/'upgrade-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print('Two actual Android gallery photos, zoom and reset verified offline',flush=True)
    tap(description('Назад'))
    tap(description('Назад'))
    # The search tab opens a single card. The book reader belongs to the
    # category/country navigation, so enter it through its actual menu.
    catalog_root()
    tap(text('Инженерные боеприпасы'))
    tap(text('Противопехотные мины'))
    tap(text('Все страны'))
    def position():
        root=tree()
        node=next(n for n in root.iter('node') if n.get('content-desc')=='Перейти к карточке')
        x1,y1,x2,y2=bounds(node)
        # Compose exports the visible counter as a sibling inside the button's
        # bounds, not as an XML child of the description node.
        for candidate in root.iter('node'):
            match=re.fullmatch(r'(\d+)\s*/\s*(\d+)',candidate.get('text',''))
            if match:
                a,b,c,d=bounds(candidate)
                if x1<=a<c<=x2 and y1<=b<d<=y2:
                    return int(match[1]),int(match[2])
        raise AssertionError('Visible reader counter missing from button bounds')
    first,total=position()
    assert first==1 and total>1
    tap(description('Следующая карточка'))
    assert position()[0]==2
    capture('reader-next-card')
    tap(description('Предыдущая карточка'))
    assert position()[0]==1
    dims=adb('shell','wm','size').decode()
    w,h=map(int,re.search(r'(\d+)x(\d+)',dims).groups())
    adb('shell','input','swipe',int(w*.80),int(h*.55),int(w*.20),int(h*.55),'450')
    time.sleep(.7)
    assert position()[0]==2, 'Left swipe did not advance the reader'
    adb('shell','input','swipe',int(w*.20),int(h*.55),int(w*.80),int(h*.55),'450')
    time.sleep(.7)
    assert position()[0]==1, 'Right swipe did not return to previous card'
    capture('reader-swipe-returned')


def main():
    global out
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--previous',type=Path,required=True)
    parser.add_argument('--signed',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--viewer-script',type=Path,required=True)
    parser.add_argument('--models',type=Path,required=True)
    parser.add_argument('--update-via-app', action='store_true')
    args=parser.parse_args();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    assert sha(args.previous)==OLD_SHA and sha(args.signed)==SIGNED_SHA
    assert not adb('shell','pm','list','packages',PACKAGE).strip(), 'Requires a fresh dedicated emulator'
    assert adb('shell','getprop','ro.kernel.qemu').decode().strip()=='1', 'Dedicated emulator is required'
    adb('root');adb('wait-for-device')
    assert adb('shell','id','-u').decode().strip()=='0', 'Cannot inspect preservation evidence without emulator root'
    for service in ('wifi','data'): adb('shell','svc',service,'disable')
    adb('shell','settings','put','global','airplane_mode_on','1')
    adb('shell','am','broadcast','-a','android.intent.action.AIRPLANE_MODE','--ez','state','true')
    time.sleep(2);offline('before-install');adb('logcat','-c')
    install=adb('install','--no-streaming',args.previous).decode()
    (out/'install-0.3.133.txt').write_text(install);assert 'Success' in install
    print('Published 0.3.133 installed on offline Android',flush=True)
    for query,title in [('TM46','ТМ-46'),('PMK40','ПМК-40')]:
        tap(search(query,title));tap(description('В избранное'));description('Убрать из избранного')
        capture('before-favorite-'+query)
        print('Favorite prepared through UI:',title,flush=True)
    appearance_dialog();tap(text('Тёмная'))
    # Compose exposes this Material switch as a checkable android.view.View.
    switch=find(lambda a:a.get('checkable')=='true' and a.get('clickable')=='true')
    if switch.get('checked')!='true': tap(switch)
    tap(text('Готово'));capture('before-appearance')
    before=snapshot('before-upgrade')
    expected_favorites={'ref-v8-tm-46','mine-audit-v25-su-pmk-40'}
    assert set(before['favorites'])==expected_favorites,before['favorites']
    assert before['appearance'].get('theme_mode')=='2' and before['appearance'].get('large_mode')=='true'
    assert len(before['cards'])==1426 and before['metadata'].get('content_version')=='190'
    print('Baseline favorites, dark theme, large mode and catalog 190 recorded',flush=True)
    if args.update_via_app:
        # Import this very module instance (also when run as __main__).
        sys.modules['recovery_android_stage3'] = sys.modules[__name__]
        from recovery_app_update_134 import update_through_app
        update_through_app()
    else:
        upgrade=adb('install','--no-streaming','-r',args.signed).decode()
        (out/'install-over-0.3.133.txt').write_text(upgrade);assert 'Success' in upgrade
    print('Android PackageManager accepted signed 0.3.134 over published 0.3.133',flush=True)
    package=adb('shell','dumpsys','package',PACKAGE).decode(errors='replace')
    (out/'installed-package.txt').write_text(package)
    assert 'versionCode=138' in package and 'versionName=0.3.134' in package
    # Launch normally so the packaged content migration runs before inspection.
    start('search_tab');find(lambda a:a.get('class')=='android.widget.EditText')
    after=snapshot('after-upgrade')
    assert after['favorites']==before['favorites'],'Favorites changed during actual APK upgrade'
    assert after['appearance']==before['appearance'],'Appearance settings changed during actual APK upgrade'
    assert len(after['cards'])==1697 and after['images']==1600
    assert after['metadata'].get('content_version')=='195'
    assert all(after['cards'].get(k)==v for k,v in before['cards'].items()),'Published cards/rowids were lost'
    start('favorites_tab');text('ТМ-46');text('ПМК-40');capture('after-favorites')
    report={'apkSha256':SIGNED_SHA,'packageName':PACKAGE,'versionName':'0.3.134','versionCode':138,
            'upgradeInstallation':('passed-actual-in-app-download-and-Android-PackageInstaller-over-published-0.3.133'
                if args.update_via_app else 'passed-actual-adb-install-r-over-published-0.3.133'),
            'favoritesPreserved':True,'favoriteIds':sorted(expected_favorites),'settingsPreserved':True,
            'preservedAppearance':before['appearance'],'fullCatalogOnAndroid':True,'contentVersion':195,
            'cards':1697,'images':1600,'preservedPublishedCardIdsAndRowids':1426,
            'galleryZoomAndSecondPhoto':False,'cardButtonsAndSwipes':False,'offline':True,
            'androidVersion':adb('shell','getprop','ro.build.version.release').decode().strip(),
            'androidApi':adb('shell','getprop','ro.build.version.sdk').decode().strip(),
            'androidModel':adb('shell','getprop','ro.product.model').decode().strip(),
            'modelVisualChecks':'pending-viewer-script'}
    (out/'upgrade-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print('Upgrade, favorites, appearance and full catalog 195 verified on Android',flush=True)
    appearance_dialog();capture('after-appearance-dialog');tap(text('Готово'));capture('after-appearance')
    try:
        verify_photo_and_navigation(report)
        report.update(galleryZoomAndSecondPhoto=True,cardButtonsAndSwipes=True)
    except Exception as error:
        report['photoNavigationError']=str(error)
        capture('photo-navigation-failure')
        traceback.print_exc()
    (out/'upgrade-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    search('TM46','ТМ-46')
    env=dict(os.environ,RECOVERY_UI_OUT=str(out/'viewer'),RECOVERY_MODELS_MANIFEST=str(args.models.resolve()))
    subprocess.run([sys.executable,str(args.viewer_script.resolve())],check=True,env=env)
    offline('after-viewers')
    crash=adb('logcat','-d','-b','crash').decode(errors='replace')
    (out/'release-crash.log').write_text(crash)
    assert 'FATAL EXCEPTION' not in crash and 'Fatal signal' not in crash,crash
    report['modelVisualChecks']='passed-pixel-contrast-relief-and-touch-rotation-on-Android'
    report['humanVisualReview']='pending-review-of-actual-Android-frames'
    (out/'upgrade-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)
    assert report['galleryZoomAndSecondPhoto'] and report['cardButtonsAndSwipes'],report


if __name__=='__main__':
    try:
        main()
    finally:
        if out is not None:
            for name,command in [('last-screen.png',('exec-out','screencap','-p')),
                                 ('device-logcat.txt',('logcat','-d'))]:
                try: (out/name).write_bytes(adb(*command))
                except Exception as error: print('Evidence capture failed:',name,type(error).__name__,file=sys.stderr)
