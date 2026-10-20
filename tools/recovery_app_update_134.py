"""Actual app download, unknown-source permission and Android PackageInstaller UI.

Called by the isolated emulator QA. No adb install of the new APK, no permission
grant through appops, and no substituted feed or local HTTP server.
"""
import hashlib
import json
import re
import time
import recovery_android_stage3 as qa


def visible(predicate, timeout=60, scroll=False):
    deadline = time.monotonic() + timeout
    direction = 1
    previous = None
    unchanged = 0
    while time.monotonic() < deadline:
        root = qa.tree()
        for node in root.iter('node'):
            if predicate(node.attrib): return node
        if scroll:
            width,height = map(int,re.search(r'(\d+)x(\d+)',qa.adb('shell','wm','size').decode()).groups())
            signature = [(n.get('text'),n.get('bounds')) for n in root.iter('node')]
            unchanged = unchanged+1 if signature == previous else 0
            if unchanged >= 2:
                direction *= -1; unchanged = 0
            previous = signature
            top,bottom = int(height*.35),int(height*.78)
            qa.adb('shell','input','swipe',width//2,bottom if direction>0 else top,
                width//2,top if direction>0 else bottom,'400')
        time.sleep(1)
    raise AssertionError('App-update UI missing: ' + repr([n.get('text') or n.get('content-desc')
        for n in root.iter('node') if n.get('text') or n.get('content-desc')]))


def update_through_app():
    qa.adb('shell','settings','put','global','airplane_mode_on','0')
    qa.adb('shell','am','broadcast','-a','android.intent.action.AIRPLANE_MODE','--ez','state','false')
    qa.adb('shell','svc','wifi','enable')
    time.sleep(5)
    qa.catalog_root();qa.tap(qa.description('Открыть меню'))
    qa.tap(visible(lambda a:a.get('text','').startswith('Обновления')))
    qa.tap(visible(lambda a:a.get('text')=='Проверить приложение', scroll=True))
    visible(lambda a:a.get('text')=='Доступна версия 0.3.134',timeout=120,scroll=True)
    qa.capture('ota-available')
    qa.tap(visible(lambda a:a.get('text')=='Скачать приложение',scroll=True))
    ready = visible(lambda a:a.get('text')=='Установить обновление',timeout=480,scroll=True)
    qa.capture('ota-downloaded-and-signature-verified')
    qa.tap(ready)
    # Android 11 opens this Settings page on the first update from the app.
    switch = visible(lambda a:a.get('package')=='com.android.settings' and a.get('checkable')=='true')
    qa.capture('ota-unknown-sources-before')
    if switch.get('checked')!='true': qa.tap(switch)
    qa.capture('ota-unknown-sources-allowed')
    qa.adb('shell','input','keyevent','4')
    # Published 0.3.133 may return to its Ready card after Settings instead of
    # launching the installer immediately. Follow the same visible second tap
    # available to a user; never replace the hand-off with adb installation.
    handoff = visible(lambda a:(a.get('package')==qa.PACKAGE and a.get('text')=='Установить обновление')
        or (a.get('package') in ('com.google.android.packageinstaller','com.android.packageinstaller')
        and a.get('text','').upper() in ('INSTALL','UPDATE','УСТАНОВИТЬ','ОБНОВИТЬ')),timeout=60)
    if handoff.get('package')==qa.PACKAGE:
        qa.capture('ota-ready-after-permission');qa.tap(handoff)
    install = visible(lambda a:a.get('package') in ('com.google.android.packageinstaller','com.android.packageinstaller')
        and a.get('text','').upper() in ('INSTALL','UPDATE','УСТАНОВИТЬ','ОБНОВИТЬ'),timeout=60)
    qa.capture('ota-system-install-confirmation');qa.tap(install)
    deadline=time.monotonic()+180
    while time.monotonic()<deadline:
        package=qa.adb('shell','dumpsys','package',qa.PACKAGE).decode(errors='replace')
        if 'versionCode=138' in package and 'versionName=0.3.134' in package: break
        time.sleep(2)
    else: raise AssertionError('Android PackageInstaller did not install 0.3.134')
    qa.capture('ota-system-install-completed')
    apkpath=qa.adb('shell','pm','path',qa.PACKAGE).decode().strip().removeprefix('package:')
    installed_sha=hashlib.sha256(qa.adb('exec-out','cat',apkpath)).hexdigest()
    assert installed_sha==qa.SIGNED_SHA, installed_sha
    evidence=dict(method='public-feed-app-download-unknown-source-settings-Android-PackageInstaller',
        feed='https://github.com/sanozhukov3737-oss/dlya-svoih-updates/releases/latest/download/latest.json',
        installedApkSha256=installed_sha, newApkInstalledViaAdb=False, package=qa.PACKAGE,
        versionName='0.3.134',versionCode=138)
    (qa.out/'ota-installation.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n')
    for service in ('wifi','data'): qa.adb('shell','svc',service,'disable')
    qa.adb('shell','settings','put','global','airplane_mode_on','1')
    qa.adb('shell','am','broadcast','-a','android.intent.action.AIRPLANE_MODE','--ez','state','true')
    time.sleep(2);qa.offline('after-ota-install')
    print('Actual public-channel in-app APK download and Android installation passed',flush=True)
