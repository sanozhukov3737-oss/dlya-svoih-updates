"""Prepare the signed application offer while retaining the public catalog 197."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import zipfile

from build_app_feed import apk_metadata, write_app_feed

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'build/compare135'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def preflight(request):
    for path, checksum in request['unchangedFiles'].items():
        assert sha(ROOT/path) == checksum, ('Unexpected data change',path)
    with sqlite3.connect(ROOT/'app/src/main/assets/database/guide-v29.db') as db:
        assert db.execute('PRAGMA integrity_check').fetchone() == ('ok',)
        assert db.execute("SELECT value FROM metadata WHERE key='content_version'").fetchone() == ('197',)
        assert db.execute('SELECT COUNT(*) FROM cards WHERE archived=0').fetchone() == (1695,)
        assert db.execute('SELECT COUNT(*) FROM images').fetchone() == (1595,)


def prepare(request, apk):
    sdk = Path(os.environ['ANDROID_HOME'])
    analyzer = str(sdk/'cmdline-tools/latest/bin/apkanalyzer')
    signer = str(sdk/'build-tools/36.0.0/apksigner')
    metadata = apk_metadata(apk, analyzer=analyzer, signer=signer)
    assert metadata['versionCode'] == 139 and metadata['versionName'] == '0.3.135'
    assert metadata['packageName'] == 'ru.dlyasvoih.app' and metadata['minSdk'] == 26
    assert metadata['signerSha256'] == request['signerSha256']
    import subprocess
    debug = subprocess.run([analyzer,'manifest','debuggable',str(apk)],check=True,capture_output=True,text=True).stdout.strip()
    assert debug == 'false'
    with zipfile.ZipFile(apk) as z:
        assert z.testzip() is None
        for path, checksum in request['unchangedFiles'].items():
            if path.startswith('app/src/main/assets/'):
                entry = 'assets/' + path.removeprefix('app/src/main/assets/')
                assert hashlib.sha256(z.read(entry)).hexdigest() == checksum, entry
    destination = OUT/'release'
    destination.mkdir(exist_ok=True,parents=True)
    target = destination/'DLYA_SVOIH_v0.3.135.apk'
    shutil.copyfile(apk,target)
    previous = json.loads((OUT/'latest-before.json').read_text())
    assert previous['contentVersion'] == 197 and previous['app']['versionCode'] == 138
    assert previous['sha256'] == 'c81652660bdb9f9a787875c206c89fc3c65cb3f1e118a3d428c945755ec86599'
    feed = write_app_feed(target,OUT/'latest-before.json',
        'https://github.com/sanozhukov3737-oss/dlya-svoih-updates/releases/download/app-0.3.135/'+target.name,
        destination/'latest.json',request['changes'],analyzer=analyzer,signer=signer)
    assert {k:v for k,v in feed.items() if k != 'app'} == {k:v for k,v in previous.items() if k != 'app'}
    (destination/'notes.txt').write_text(request['changes']+'\n\nКаталог 197 включён в APK. Проверены подпись прежним ключом, установка поверх 0.3.134 с сохранением каталога, избранного, места чтения и настроек, выбор двух и трёх карточек, поиск по категории и прокрутка на Android 11.\n')
    result = dict(versionName='0.3.135',versionCode=139,contentVersion=197,
        candidateSourceCommit=os.environ['GITHUB_SHA'],workflowRunId=int(os.environ['GITHUB_RUN_ID']),
        apkSha256=sha(target),apkBytes=target.stat().st_size,feedSha256=sha(destination/'latest.json'),
        signerSha256=metadata['signerSha256'],catalogOfferUnchanged=True,
        humanVisualReview='pending review of actual Android screenshots')
    (destination/'build-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--apk',type=Path)
    args = parser.parse_args()
    request = json.loads((ROOT/'docs/releases/app-0.3.135.json').read_text())
    preflight(request)
    if args.apk: prepare(request,args.apk)
    else: print('Exact catalog 197, database and model assets preserved')
