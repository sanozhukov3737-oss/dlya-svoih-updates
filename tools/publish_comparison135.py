"""Publish the exact signed artifact after review of actual Android screenshots."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

from build_app_feed import apk_metadata

REPO = 'sanozhukov3737-oss/dlya-svoih-updates'
TAG = 'app-0.3.135'
ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT/'build/comparison135-publish'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(*args):
    return subprocess.run(list(map(str,args)),check=True,capture_output=True,text=True,timeout=300).stdout


def verify_published(request):
    release = json.loads(run('gh','api',f'repos/{REPO}/releases/tags/{TAG}'))
    latest = json.loads(run('gh','api',f'repos/{REPO}/releases/latest'))
    assert not release['draft'] and latest['tag_name'] == TAG
    assets = {a['name']:a for a in release['assets']}
    assert assets['DLYA_SVOIH_v0.3.135.apk']['digest'] == 'sha256:'+request['apkSha256']
    assert assets['latest.json']['digest'] == 'sha256:'+request['feedSha256']
    address = f'https://github.com/{REPO}/releases/latest/download/latest.json'
    for attempt in range(8):
        fetch = urllib.request.Request(address,headers={'Cache-Control':'no-cache','Pragma':'no-cache'})
        with urllib.request.urlopen(fetch,timeout=90) as response: raw = response.read(65537)
        feed = json.loads(raw)
        if hashlib.sha256(raw).hexdigest() == request['feedSha256']: break
        print('Waiting for public redirect cache; offered app:',feed.get('app',{}).get('versionName'),flush=True)
        time.sleep(8)
    else: raise AssertionError('Public update channel still differs from the uploaded feed')
    assert feed['app']['versionCode'] == 139 and feed['contentVersion'] == 197
    assert feed['app']['signerSha256'] == '2f0a0908f269bc039311edb58fca8863347f1e4c3a7cfaddd909991cf1f0b509'
    assert feed['sha256'] == 'c81652660bdb9f9a787875c206c89fc3c65cb3f1e118a3d428c945755ec86599'
    WORK.mkdir(parents=True,exist_ok=True)
    report = dict(versionName='0.3.135',versionCode=139,contentVersion=197,
        apkSha256=request['apkSha256'],feedSha256=request['feedSha256'],
        releasePublished=True,updateChannelVerified=True,assetDigestsMatchVerifiedBuild=True,
        releaseUrl=release['html_url'],buildWorkflowRunId=request['workflowRunId'],
        visualReview=request['visualReview'])
    (WORK/'public-channel-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False))


def main():
    request = json.loads((ROOT/'docs/releases/app-0.3.135-verified.json').read_text())
    assert request['visualReview'] == 'passed'
    for path,digest in request['reviewedScreens'].items():
        assert sha(ROOT/path) == digest, ('Reviewed screenshot changed',path)
    if '--verify-published' in sys.argv:
        verify_published(request)
        return
    source = ROOT/'build/comparison135-candidate'
    apk = source/'DLYA_SVOIH_v0.3.135.apk'
    feed_path = source/'latest.json'
    assert sha(apk) == request['apkSha256'] and sha(feed_path) == request['feedSha256']
    result = json.loads((source/'build-result.json').read_text())
    assert result['candidateSourceCommit'] == request['candidateSourceCommit']
    assert result['workflowRunId'] == request['workflowRunId']
    workflow = json.loads(run('gh','api',f'repos/{REPO}/actions/runs/{request["workflowRunId"]}'))
    assert workflow['conclusion'] == 'success' and workflow['head_sha'] == request['candidateSourceCommit']
    sdk = Path(os.environ['ANDROID_HOME'])
    identity = apk_metadata(apk,analyzer=str(sdk/'cmdline-tools/latest/bin/apkanalyzer'),
        signer=str(sdk/'build-tools/36.0.0/apksigner'))
    assert identity['versionName'] == '0.3.135' and identity['versionCode'] == 139
    assert identity['signerSha256'] == '2f0a0908f269bc039311edb58fca8863347f1e4c3a7cfaddd909991cf1f0b509'
    address = f'https://github.com/{REPO}/releases/latest/download/latest.json'
    with urllib.request.urlopen(address,timeout=90) as response: previous = json.loads(response.read(65537))
    feed = json.loads(feed_path.read_text())
    assert previous['app']['versionCode'] == 138 and previous['contentVersion'] == 197
    assert {k:v for k,v in feed.items() if k != 'app'} == {k:v for k,v in previous.items() if k != 'app'}
    assert feed['app']['sha256'] == sha(apk) and feed['app']['versionCode'] == 139
    assert feed['app']['bytes'] == apk.stat().st_size
    WORK.mkdir(parents=True,exist_ok=True)
    run('gh','release','create',TAG,apk,feed_path,'--repo',REPO,'--draft',
        '--target',request['candidateSourceCommit'],'--title','ДЛЯ СВОИХ — 0.3.135',
        '--notes-file',source/'notes.txt')
    check = WORK/'download-check'
    check.mkdir(exist_ok=True)
    run('gh','release','download',TAG,'--repo',REPO,'--pattern',apk.name,'--pattern','latest.json','--dir',check)
    assert sha(check/apk.name) == request['apkSha256']
    assert sha(check/'latest.json') == request['feedSha256']
    report = dict(versionName='0.3.135',versionCode=139,contentVersion=197,
        apkSha256=request['apkSha256'],apkBytes=apk.stat().st_size,feedSha256=request['feedSha256'],
        signerSha256=identity['signerSha256'],workflowRunId=request['workflowRunId'],
        visualReview='passed on actual signed Android screenshots',reviewedScreens=request['reviewedScreens'],
        uploadedBytesVerified=True,catalogOfferUnchanged=True)
    proof = WORK/'publication-verification.json'
    proof.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    run('gh','release','upload',TAG,proof,'--repo',REPO)
    run('gh','release','edit',TAG,'--repo',REPO,'--draft=false','--latest')
    for attempt in range(5):
        with urllib.request.urlopen(address,timeout=90) as response: public = response.read(65537)
        if hashlib.sha256(public).hexdigest() == request['feedSha256']: break
        time.sleep(2 ** attempt)
    else: raise AssertionError('Public update channel differs')
    report.update(updateChannelVerified=True,releaseUrl=f'https://github.com/{REPO}/releases/tag/{TAG}')
    (WORK/'public-channel-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False))


if __name__ == '__main__': main()
