"""Publish the already tested signed 0.3.137 APK, without rebuilding or signing."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

from build_app_feed import write_app_feed

ROOT = Path(__file__).resolve().parents[1]
REPO = 'sanozhukov3737-oss/dlya-svoih-updates'
TAG = 'app-0.3.137'
NAME = 'DLYA_SVOIH_v0.3.137.apk'
WORK = ROOT / 'build/lazy137-publish'
SOURCE = ROOT / 'build/lazy137-candidate'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(*args, optional=False):
    result = subprocess.run(list(map(str, args)), capture_output=True, text=True, timeout=300)
    if optional and result.returncode and '404' in result.stderr:
        return None
    if result.returncode:
        print(result.stderr[-6000:], file=sys.stderr, flush=True)
        result.check_returncode()
    return result.stdout


def api(path, optional=False):
    raw = run('gh', 'api', f'repos/{REPO}/{path}', optional=optional)
    return json.loads(raw) if raw is not None else None


def release_for_tag():
    # The by-tag endpoint excludes unpublished releases. The authenticated
    # releases list includes the draft we must verify before publishing.
    matches = [r for r in api('releases?per_page=100') if r['tag_name'] == TAG]
    assert len(matches) <= 1
    return matches[0] if matches else None


def fetch(url):
    request = urllib.request.Request(url, headers={'Cache-Control': 'no-cache', 'Pragma': 'no-cache'})
    with urllib.request.urlopen(request, timeout=90) as response:
        data = response.read(65537)
    assert len(data) <= 65536, 'Update feed exceeds its size limit'
    return data


def source_context(candidate, current):
    comparison = api(f'compare/{candidate}...{current}')
    assert comparison['status'] in ('ahead', 'identical')
    assert len(comparison['files']) < 300
    assert all(f['filename'].startswith(('tools/', '.github/workflows/', 'docs/', 'research/'))
               for f in comparison['files']), 'App sources differ from the tested APK'


def verify_evidence(request):
    folder = ROOT / 'research/lazy-comparison-137'
    assert sha(folder/'verification.json') == request['verificationSha256']
    assert sha(folder/'visual-review.json') == request['visualReviewSha256']
    verification = json.loads((folder/'verification.json').read_text())
    ledger = json.loads((folder/'visual-review.json').read_text())
    assert ledger['status'] == 'passed' and len(ledger['images']) == 11
    for image in ledger['images']:
        assert image['status'] == 'passed' and sha(folder/image['path']) == image['sha256']
    candidate = request['candidateSourceCommit']
    build = api(f'actions/runs/{request["workflowRunId"]}')
    assert build['head_sha'] == candidate
    jobs = api(f'actions/runs/{request["workflowRunId"]}/jobs')['jobs']
    assert any(j['id'] == verification['buildJobId'] and j['name'] == 'build'
               and j['conclusion'] == 'success' for j in jobs)
    artifact = api(f'actions/artifacts/{verification["buildArtifact"]["id"]}')
    assert artifact['digest'] == 'sha256:' + verification['buildArtifact']['sha256']
    assert artifact['name'] == 'lazy137-build' and not artifact['expired']
    for android in (26, 36):
        entry = verification['apis'][str(android)]
        evidence = json.loads((folder/f'api{android}/result.json').read_text())
        assert evidence['passed'] is True and evidence['api'] == android and evidence['androidTests'] == 14
        assert evidence['apkSha256'] == request['apkSha256'] and evidence['candidateSourceCommit'] == candidate
        assert all(evidence['checks'][k] for k in ('signedUpgradeAndSavedState', 'applyWhileKeyboardOpen',
            'comparisonTwoAndThree', 'selectionSurvivesFontConfiguration', 'favoritePersistedToDatabase'))
        workflow = api(f'actions/runs/{entry["runId"]}')
        assert workflow['head_sha'] == entry['verificationSourceCommit']
        if android == 26:
            assert workflow['conclusion'] == 'success'
        jobs = api(f'actions/runs/{entry["runId"]}/jobs')['jobs']
        assert any(j['id'] == entry['jobId'] and j['conclusion'] == 'success' for j in jobs)
        source_context(candidate, entry['verificationSourceCommit'])
    assert api('actions/runs/39646189140')['conclusion'] == 'success'
    source_context(candidate, os.environ['GITHUB_SHA'])
    return verification, ledger


def main():
    request = json.loads((ROOT/'docs/releases/app-0.3.137-verified.json').read_text())
    verification, ledger = verify_evidence(request)
    WORK.mkdir(parents=True, exist_ok=True)
    apk = SOURCE / NAME
    assert sha(apk) == request['apkSha256'] and apk.stat().st_size == request['apkBytes']
    metadata = json.loads((SOURCE/'build-result.json').read_text())
    assert metadata['candidateSourceCommit'] == request['candidateSourceCommit']
    assert metadata['workflowRunId'] == request['workflowRunId']
    previous_raw = fetch(f'https://github.com/{REPO}/releases/download/app-0.3.136/latest.json')
    assert hashlib.sha256(previous_raw).hexdigest() == request['previousFeedSha256']
    previous = json.loads(previous_raw)
    assert previous['app']['versionCode'] == 140 and previous['contentVersion'] == 197
    previous_file = WORK/'previous-latest.json'; previous_file.write_bytes(previous_raw)
    feed_file = WORK/'latest.json'
    sdk = Path(os.environ['ANDROID_HOME'])
    analyzer = str(sdk/'cmdline-tools/latest/bin/apkanalyzer')
    feed = write_app_feed(apk, previous_file, f'https://github.com/{REPO}/releases/download/{TAG}/{NAME}',
        feed_file, request['changes'], analyzer=analyzer, signer=str(sdk/'build-tools/36.0.0/apksigner'))
    assert feed['app']['versionName'] == '0.3.137' and feed['app']['versionCode'] == 141
    assert feed['app']['sha256'] == request['apkSha256'] and feed['app']['signerSha256'] == request['signerSha256']
    assert feed['app']['packageName'] == 'ru.dlyasvoih.app' and feed['app']['minSdk'] == 26
    assert run(analyzer, 'manifest', 'debuggable', apk).strip() == 'false'
    assert {k:v for k,v in feed.items() if k != 'app'} == {k:v for k,v in previous.items() if k != 'app'}
    feed_sha = sha(feed_file)
    canonical = f'https://github.com/{REPO}/releases/latest/download/latest.json'
    current_raw = fetch(canonical)
    assert hashlib.sha256(current_raw).hexdigest() in (request['previousFeedSha256'], feed_sha)
    notes = WORK/'notes.txt'; notes.write_text(request['notes']+'\n')
    release = release_for_tag()
    if release is None:
        assert api('releases/latest')['tag_name'] == 'app-0.3.136'
        run('gh', 'release', 'create', TAG, '--repo', REPO, '--draft', '--target', os.environ['GITHUB_SHA'],
            '--title', 'ДЛЯ СВОИХ — 0.3.137', '--notes-file', notes)
        release = release_for_tag()
        assert release is not None and release['draft']
    for file in (apk, feed_file):
        existing = next((a for a in release['assets'] if a['name'] == file.name), None)
        if existing:
            assert existing['digest'] == 'sha256:' + sha(file), 'Existing release asset differs'
        else:
            assert release['draft'], 'A published release cannot gain missing primary assets'
            run('gh', 'release', 'upload', TAG, file, '--repo', REPO)
    check = WORK/'download-check'; check.mkdir(exist_ok=True)
    run('gh', 'release', 'download', TAG, '--repo', REPO, '--pattern', NAME, '--pattern', 'latest.json',
        '--dir', check, '--skip-existing')
    assert sha(check/NAME) == request['apkSha256'] and sha(check/'latest.json') == feed_sha
    # A draft need not have a tag reference yet. Its pinned target is the
    # publication context; the real tag is checked after the release is public.
    tag_commit = release['target_commitish']
    assert len(tag_commit) == 40 and all(c in '0123456789abcdef' for c in tag_commit)
    source_context(request['candidateSourceCommit'], tag_commit)
    report = dict(versionName='0.3.137', versionCode=141, contentVersion=197,
        apkSha256=request['apkSha256'], apkBytes=apk.stat().st_size, feedSha256=feed_sha,
        feedBytes=feed_file.stat().st_size, signerSha256=feed['app']['signerSha256'],
        artifactSourceCommit=request['candidateSourceCommit'], releaseTagCommit=tag_commit,
        buildWorkflowRunId=request['workflowRunId'], androidVerification=verification['apis'],
        reviewedScreens=ledger['images'], uploadedBytesVerified=True, catalogOfferUnchanged=True,
        apkUrl=feed['app']['url'], updateChannelUrl=canonical,
        releaseUrl=f'https://github.com/{REPO}/releases/tag/{TAG}')
    proof = WORK/'publication-verification.json'
    proof.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    if not any(a['name'] == proof.name for a in release['assets']):
        run('gh', 'release', 'upload', TAG, proof, '--repo', REPO)
    if release['draft']:
        run('gh', 'release', 'edit', TAG, '--repo', REPO, '--draft=false', '--latest')
    release = api(f'releases/tags/{TAG}')
    assert not release['draft'] and api('releases/latest')['tag_name'] == TAG
    assert api(f'git/ref/tags/{TAG}')['object']['sha'] == tag_commit
    assets = {a['name']:a for a in release['assets']}
    assert assets[NAME]['digest'] == 'sha256:'+request['apkSha256']
    assert assets['latest.json']['digest'] == 'sha256:'+feed_sha
    for attempt in range(8):
        live = fetch(canonical)
        if hashlib.sha256(live).hexdigest() == feed_sha:
            break
        print('Waiting for public update redirect cache', flush=True)
        time.sleep(8)
    else:
        raise AssertionError('Canonical update feed does not match the published asset')
    assert json.loads(live) == feed
    with urllib.request.urlopen(feed['app']['url'], timeout=90) as response:
        assert response.read(4) == b'PK\x03\x04', 'Public APK download did not return a ZIP/APK'
    report.update(releasePublished=True, updateChannelVerified=True, publicApkDownloadVerified=True,
        publicationWorkflowRunId=int(os.environ['GITHUB_RUN_ID']))
    (WORK/'public-channel-verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
