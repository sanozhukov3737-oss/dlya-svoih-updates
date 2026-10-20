#!/usr/bin/env python3
"""Collect reproducible evidence on an explicitly selected physical Android phone.

Does not install, downgrade, uninstall, clear data, root, grant permissions or
change network/settings. Output can contain personal favorites: keep it private.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from datetime import datetime, timezone

PACKAGE = 'ru.dlyasvoih.app'
VERSIONS = {'before': ('0.3.133', 137,
    '8cff50f9d76dbeec261ca928603277bdf540d0d0b42913bde919a82ce8d5d49f'),
    'after': ('0.3.134', 138,
    '300b77deaee3348e05a0135bf0079414c07dc2e15a7dcfd9b1239a8cef99298f')}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adb', type=Path)
    parser.add_argument('--serial', required=True)
    parser.add_argument('--phase', choices=VERSIONS, required=True)
    parser.add_argument('--label', required=True, help='e.g. favorites, appearance, gallery, m14-rotated')
    parser.add_argument('--out', type=Path, default=Path('build/physical-android-0.3.134'))
    parser.add_argument('--require-offline', action='store_true')
    args=parser.parse_args()
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,60}',args.label): parser.error('Use a short ASCII label')
    adb=args.adb or shutil.which('adb')
    if not adb:
        sdk=Path(os.environ.get('LOCALAPPDATA',''))/'Android/Sdk/platform-tools/adb.exe'
        if sdk.is_file(): adb=sdk
    if not adb: parser.error('Pass --adb with the path to Android SDK platform-tools/adb.exe')
    def run(*command):
        return subprocess.run([str(adb),'-s',args.serial,*command],capture_output=True,timeout=90,check=True).stdout
    assert run('get-state').decode().strip()=='device','Authorize this PC on the phone first'
    assert run('shell','getprop','ro.kernel.qemu').decode().strip()!='1','A physical phone is required'
    package=run('shell','dumpsys','package',PACKAGE).decode(errors='replace')
    version, code, expected_sha=VERSIONS[args.phase]
    assert re.search(r'\bversionName='+re.escape(version)+r'\s',package), (
        'Expected '+version+'. Never downgrade or delete the installed app to satisfy this check.')
    assert re.search(r'\bversionCode='+str(code)+r'\b',package),'Unexpected versionCode'
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    dest=args.out/(stamp+'-'+args.phase+'-'+args.label);dest.mkdir(parents=True,exist_ok=False)
    (dest/'package.txt').write_text(package,encoding='utf-8')
    props=run('shell','getprop').decode(errors='replace');(dest/'device.txt').write_text(props,encoding='utf-8')
    connectivity=run('shell','dumpsys','connectivity').decode(errors='replace')
    (dest/'connectivity.txt').write_text(connectivity,encoding='utf-8')
    run('shell','uiautomator','dump','/sdcard/dlya-svoih-phone-check.xml')
    (dest/'screen.xml').write_bytes(run('exec-out','cat','/sdcard/dlya-svoih-phone-check.xml'))
    (dest/'screen.png').write_bytes(run('exec-out','screencap','-p'))
    (dest/'crash.log').write_bytes(run('logcat','-d','-b','crash'))
    paths=run('shell','pm','path',PACKAGE).decode().splitlines()
    assert len(paths)==1 and paths[0].startswith('package:'),'Unexpected split APK layout'
    raw=run('exec-out','cat',paths[0][len('package:'):].strip())
    digest=hashlib.sha256(raw).hexdigest()
    assert digest==expected_sha,'Installed APK differs from the checked public release: '+digest
    no_network=bool(re.search(r'Active default network:\s*(none|null|-1)\b',connectivity,re.I))
    evidence=dict(phase=args.phase,label=args.label,timestampUtc=stamp,physicalDevice=True,
        package=PACKAGE,versionName=version,versionCode=code,installedApkSha256=digest,
        noActiveDefaultNetwork=no_network,manualFunctionalReview='not-asserted-by-capture-script',
        preservationComparison='compare-before-and-after-screens-manually')
    (dest/'evidence.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    if args.require_offline: assert no_network,'Disable Wi-Fi and mobile data, then capture again'
    print(str(dest.resolve()))


if __name__=='__main__': main()
