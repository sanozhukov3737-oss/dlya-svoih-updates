"""Package inspected Android frames and immutable release verification metadata."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'build/models138'

def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def main():
    proof = WORK / 'release-proof'
    selected = json.loads((proof / 'models/result.json').read_text())
    registry = json.loads((ROOT / 'app/src/main/assets/viewer3d/models.json').read_text())['models']
    source = {m['id']: m for m in registry}
    assert len(source) == len(selected['models']) == 615
    assert {m['id'] for m in selected['models']} == set(source)
    actions = json.loads((WORK / 'evidence/actions.json').read_text())
    corrected = actions['renderRuns'][-1]
    assert len([j for j in corrected['jobs'] if j['name'].startswith('render (') and j['conclusion'] == 'success']) == 8
    records = []
    for m in sorted(selected['models'], key=lambda m: m['id']):
        assert m.get('humanReview', m.get('visualReview')) == 'passed' and m['passed']
        hashes = {k: sha(proof / 'models' / m[k]) for k in ['initial', 'rotated']}
        assert hashes['initial'] != hashes['rotated']
        records.append({**{k: v for k, v in m.items() if k != 'humanReview'},
            'visualReview': 'passed', 'frameSha256': hashes,
            'glbSha256': source[m['id']]['packagedSha256']})
    manifest = {'status': 'passed', 'reviewer': 'Codex visual inspection of actual Android screenshots',
        'modelCount': 615, 'frameCount': 1230, 'models': records,
        'note': '464 inspected pairs from run 40479531721 plus 151 replacement pairs from run 40481937887. Loading-caption frames were excluded. Original PNGs are unchanged.'}
    (proof / 'models-review.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
    selected['status'] = 'passed'
    selected['models'] = records
    (proof / 'models/result.json').write_text(json.dumps(selected, indent=2)+'\n')
    subprocess.run([sys.executable, str(ROOT / 'tools/review_frames138.py'), str(proof / 'models'),
        '--out', str(proof / 'contact-sheets'), '--compact'], check=True)
    (proof / 'contact-sheets/review.json').unlink()
    for api in [26, 36]:
        src = WORK / f'proofs/upgrade-api{api}/upgrade-proof'
        dest = proof / f'upgrade-api{api}'
        dest.mkdir(exist_ok=True)
        for name in ['result.json', 'contract-tests.txt', 'release-gallery.png', 'release-pmn.png', 'release-pmn-rotated.png']:
            shutil.copy2(src / name, dest / name)
    (proof / 'actions.json').write_text(json.dumps(actions, indent=2)+'\n')
    (proof / 'README.txt').write_text('Actual offline Android screenshots, not desktop or generated previews.\n'
        'All 615 model pairs were inspected for visible body, relief, framing, and rotation.\n'
        'Collection frames use the debug APK from the same build source and exact GLB payload as the signed full release.\n'
        'The signed release APK itself was installed, searched, opened and rotated on Android 8 and Android 16.\n'
        'The complete collection was rendered without network on Android 11. No physical phone was available.\n'
        'Contact sheets crop surrounding background for convenience. models/ retains original full PNGs.\n'
        'The 151 initial loading-caption captures were rejected and their pairs replaced; see per-model sourceRunId.\n')
    out = WORK / 'publication'
    archive = out / 'DLYA_SVOIH_0.3.138_Android_Views.zip'
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=3) as z:
        for path in sorted(proof.rglob('*')):
            if path.is_file(): z.write(path, path.relative_to(proof))
    build = json.loads((WORK / 'apks/build-result.json').read_text())
    report = {'status': 'passed', 'versionName': '0.3.138', 'date': actions['date'],
        'modelCount': 615, 'newModelCount': 596, 'mappedCardCount': 511, 'separateUnconfirmedVisuals': 44,
        'catalogVersion': 197, 'catalogCards': 1695, 'catalogImages': 1595,
        'fullApk': build['full'], 'bridgeApk': build['bridge'],
        'modelsRegistrySha256': sha(ROOT / 'app/src/main/assets/viewer3d/models.json'),
        'databaseSha256': sha(ROOT / 'app/src/main/assets/database/guide-v29.db'),
        'reviewManifestSha256': sha(proof / 'models-review.json'),
        'proofArchive': {'filename': archive.name, 'bytes': archive.stat().st_size, 'sha256': sha(archive)},
        'visualReview': {'status': 'passed', 'modelPairs': 615, 'actualAndroidFrames': 1230,
            'renderApk': 'debug APK from signed release build source and identical GLB payload',
            'reviewer': manifest['reviewer'], 'networkBlocked': True},
        'upgradeChecks': [json.loads((proof / f'upgrade-api{api}/result.json').read_text()) for api in [26,36]],
        'actions': actions, 'physicalPhoneTested': False}
    for d in report['upgradeChecks']: assert d['passed'] and all(d['checks'].values())
    (out / 'DLYA_SVOIH_0.3.138_Verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(report['proofArchive']))

if __name__ == '__main__': main()
