"""Publish the exact signed and Android-checked recovery APK; never rebuild or resign it."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile

REPO = 'sanozhukov3737-oss/dlya-svoih-updates'
TAG = 'app-0.3.134'
SOURCE = '9971bd151d5bc3fd49399cadf7019540b497c3f8'
TREE = '5e9889be28c0e03288b82baae67cb56f665a2c62'
BRANCH = 'recovery/source-snapshot-0.3.134-20261020'
APK_SHA = '300b77deaee3348e05a0135bf0079414c07dc2e15a7dcfd9b1239a8cef99298f'
CERT = '2f0a0908f269bc039311edb58fca8863347f1e4c3a7cfaddd909991cf1f0b509'
DB_SHA = 'fbbb7a38d77b09b963520011ef64b8111991e03ed1b2ae6277ec335761a107ed'
FEED133_SHA = 'd10e8849a94d6d19ce3b70a2795f35d1e8c6a9b2d2bf7e60bb76f5f868214dbf'
BASE = f'https://github.com/{REPO}/releases/download/{TAG}/'


def run(*args, **kwargs):
    return subprocess.run([str(a) for a in args], check=True, **kwargs)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def dump(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def api(path, optional=False):
    result = subprocess.run(['gh', 'api', '--method', 'GET', f'repos/{REPO}/{path}'],
                            capture_output=True, text=True)
    if result.returncode and optional and 'HTTP 404' in result.stderr:
        return None
    if result.returncode:
        raise RuntimeError(result.stderr)
    return json.loads(result.stdout)


def asset(asset_id, path, size, digest):
    with path.open('wb') as stream:
        run('gh', 'api', '--method', 'GET', '-H', 'Accept: application/octet-stream',
            f'repos/{REPO}/releases/assets/{asset_id}', stdout=stream)
    assert path.stat().st_size == size and sha(path) == digest, path


def public_download(url, target, expected_sha):
    for attempt in range(4):
        try:
            request = urllib.request.Request(url, headers={'Cache-Control': 'no-cache'})
            with urllib.request.urlopen(request, timeout=120) as response, target.open('wb') as stream:
                shutil.copyfileobj(response, stream)
            assert sha(target) == expected_sha, url
            return
        except Exception:
            if attempt == 3:
                raise
            time.sleep(2 * (attempt + 1))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--sdk', type=Path, required=True)
    args = parser.parse_args()
    work = args.work.resolve()
    work.mkdir(parents=True, exist_ok=True)
    out = work / 'release'
    out.mkdir(exist_ok=True)
    apk_zip, source_zip = work / 'signed.zip', work / 'source.zip'
    asset(658954242, apk_zip, 143924779, '03ae0c9421380986e43d7ae7d4d2f112466edfa53b2379c3b3d19f01a89af80a')
    asset(659015127, source_zip, 196306677, 'fd6ee8a047a341bd589721675c43fe54e31bf85cfe517a0367157e029e9a0646')
    apk = out / 'DLYA_SVOIH_v0.3.134.apk'
    with zipfile.ZipFile(apk_zip) as z:
        apk.write_bytes(z.read(apk.name))
    assert apk.stat().st_size == 144646769 and sha(apk) == APK_SHA
    bundle = work / 'source.bundle'
    with zipfile.ZipFile(source_zip) as z, bundle.open('wb') as stream:
        with z.open('DLYA_SVOIH_0.3.134_RECOVERED_SOURCE.bundle') as original:
            shutil.copyfileobj(original, stream)
    assert sha(bundle) == '00323f8d1ce7232d2c033b17f5f6b4bee2690187feab77beaa82221c1a6c70cb'
    source = work / 'source'
    run('git', 'clone', '--quiet', '--branch', BRANCH, bundle, source)
    for expression, expected in [('HEAD', SOURCE), ('HEAD^{tree}', TREE)]:
        assert subprocess.check_output(['git', '-C', str(source), 'rev-parse', expression], text=True).strip() == expected
    run('git', '-C', source, 'fsck', '--full')
    proof = json.loads((source / 'research/recovery-stage-3/android-final/release-readiness.json').read_text())
    assert proof['apkSha256'] == APK_SHA and proof['signatureVerified']
    assert proof['androidRuntimeChecks'] == 'passed' and proof['visualInspection'] == 'passed-8-actual-Android-frames'
    assets = source / 'app/src/main/assets'
    with zipfile.ZipFile(apk) as z:
        names = [n for n in z.namelist() if n.startswith('assets/') and not n.endswith('/') and not n.startswith('assets/dexopt/')]
        assert len(names) == 3640
        for n in names:
            assert (assets / n[7:]).read_bytes() == z.read(n), n
        assert hashlib.sha256(z.read('assets/database/guide-v29.db')).hexdigest() == DB_SHA
    sys.path.insert(0, str(source / 'tools'))
    from build_app_feed import apk_metadata, write_app_feed
    from build_update_feed import write_feed
    from pack_restored_catalog import make_pack
    signer = args.sdk / 'build-tools/36.0.0/apksigner'
    analyzer = args.sdk / 'cmdline-tools/latest/bin/apkanalyzer'
    metadata = apk_metadata(apk, analyzer=str(analyzer), signer=str(signer))
    assert metadata == dict(packageName='ru.dlyasvoih.app', versionCode=138, versionName='0.3.134', minSdk=26, signerSha256=CERT), metadata
    assert subprocess.check_output([str(analyzer), 'manifest', 'debuggable', str(apk)], text=True).strip() == 'false'
    run(args.sdk / 'build-tools/36.0.0/zipalign', '-c', '4', apk)
    for pattern in ('test_app_feed.py', 'test_update_feed.py'):
        run(sys.executable, '-m', 'unittest', 'discover', '-s', source / 'tools', '-p', pattern)
    previous = work / 'latest-0.3.133.json'
    public_download(f'https://github.com/{REPO}/releases/download/app-0.3.133/latest.json', previous, FEED133_SHA)
    old = json.loads(previous.read_text())
    assert old['contentVersion'] == 190 and old['app']['versionCode'] == 137 and old['app']['signerSha256'] == CERT
    request = json.loads((source / 'content/releases/app-0.3.134.json').read_text())
    changes = request['changes'] + ' Исправлены импорт полного каталога и отображение 3D на Android.'
    pack = out / 'catalog-195.zip'
    make_pack(assets, pack, 195, 1697, 1600)
    with zipfile.ZipFile(pack) as z:
        assert hashlib.sha256(z.read('guide.db')).hexdigest() == DB_SHA
    catalog_feed = work / 'catalog-feed.json'
    write_feed(pack, BASE + pack.name, catalog_feed, changes, 138, previous)
    feed = write_app_feed(apk, catalog_feed, BASE + apk.name, out / 'latest.json', changes,
                          analyzer=str(analyzer), signer=str(signer))
    assert feed['contentVersion'] == 195 and feed['app']['sha256'] == APK_SHA
    checks = dict(packageName='ru.dlyasvoih.app', versionName='0.3.134', versionCode=138,
                  apkSha256=APK_SHA, certificateSha256=CERT, sourceCommit=SOURCE, sourceTree=TREE,
                  applicationSourceCommit='a8c3b76f8921ffe05e4beaad7b6ba33891200642',
                  contentVersion=195, cards=1697, images=1600, offlineModels=19,
                  originalSignedApkPreserved=True, originalCatalogDatabasePreserved=True,
                  productionAssetMatches=3640, signingRun=39403888993, androidRun=39404271107,
                  androidRuntimeChecks='passed', fourModelPairsVisuallyReviewed=True,
                  androidWorkflowConclusion='cancelled-after-app-checks-at-emulator-shutdown;proof-upload-success',
                  physicalDeviceTested=False, androidApiTested=30)
    dump(out / 'release-verification.json', checks)
    files = [apk, pack, out / 'latest.json', out / 'release-verification.json']
    (out / 'SHA256SUMS.txt').write_text(''.join(sha(f) + '  ' + f.name + '\n' for f in files))
    files.append(out / 'SHA256SUMS.txt')
    notes = work / 'notes.txt'
    notes.write_text(changes + '\n\nОбновление поверх 0.3.133 сохраняет избранное и настройки. Проверены поиск, фотографии, навигация и офлайн-работа на Android 11. Для четырёх новых 3D-моделей проверены начальный вид и вращение; авторство, лицензии и обозначение условной окраски сохранены.\n', encoding='utf-8')
    expected = {f.name: dict(bytes=f.stat().st_size, sha256=sha(f)) for f in files}
    dump(work / 'prepared-publication.json', dict(tag=TAG, sourceCommit=SOURCE, files=expected, checks=checks))

    # Serialize with the existing publication workflow; never overwrite another release.
    existing = api(f'releases/tags/{TAG}', optional=True)
    if existing is not None and not existing['draft']:
        assert {a['name']: a['digest'].removeprefix('sha256:') for a in existing['assets']} == {n: r['sha256'] for n, r in expected.items()}
    else:
        current = api('releases/latest')
        assert current['tag_name'] == 'app-0.3.133', 'Channel changed since approved baseline; stop before publication'
        remote = api(f'git/ref/heads/{BRANCH}', optional=True)
        if remote is None:
            run('git', 'fetch', '--no-tags', bundle, f'refs/heads/{BRANCH}:refs/remotes/recovery/publish134')
            run('git', 'push', 'origin', f'{SOURCE}:refs/heads/{BRANCH}')
        else:
            assert remote['object']['sha'] == SOURCE
        tag = api(f'git/ref/tags/{TAG}', optional=True)
        if tag is not None:
            assert tag['object']['type'] == 'commit' and tag['object']['sha'] == SOURCE
        if existing is None:
            run('gh', 'release', 'create', TAG, *files, '--repo', REPO, '--target', SOURCE,
                '--draft', '--title', TAG, '--notes-file', notes)
        else:
            assert existing['target_commitish'] == SOURCE
            known = {a['name']: a for a in existing['assets']}
            assert set(known).issubset(expected)
            for name, value in known.items():
                assert value['digest'] == 'sha256:' + expected[name]['sha256'] and value['size'] == expected[name]['bytes']
            missing = [f for f in files if f.name not in known]
            if missing:
                run('gh', 'release', 'upload', TAG, *missing, '--repo', REPO)
        check = work / 'downloaded-draft'
        run('gh', 'release', 'download', TAG, '--repo', REPO, '--dir', check)
        for name, record in expected.items():
            assert (check / name).stat().st_size == record['bytes'] and sha(check / name) == record['sha256'], name
        assert api('releases/latest')['tag_name'] == 'app-0.3.133'
        run('gh', 'release', 'edit', TAG, '--repo', REPO, '--draft=false', '--prerelease=false', '--latest')
    published = api('releases/latest')
    assert published['tag_name'] == TAG and not published['draft'] and not published['prerelease']
    downloaded = work / 'downloaded-public'
    downloaded.mkdir(exist_ok=True)
    for name, record in expected.items():
        public_download(BASE + name, downloaded / name, record['sha256'])
        assert (downloaded / name).stat().st_size == record['bytes']
    public_download(f'https://github.com/{REPO}/releases/latest/download/latest.json', downloaded / 'channel.json', expected['latest.json']['sha256'])
    dump(work / 'publication-result.json', dict(published=True, tag=TAG, releaseId=published['id'],
         sourceCommit=SOURCE, files=expected, publicDownloadsVerified=True, latestChannelVerified=True,
         releaseUrl=published['html_url'], apkUrl=BASE + apk.name, checks=checks))
    print('PUBLISHED AND PUBLIC DOWNLOADS VERIFIED: ' + BASE + apk.name, flush=True)


if __name__ == '__main__':
    main()
