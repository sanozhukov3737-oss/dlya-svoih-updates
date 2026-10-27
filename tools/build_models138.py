"""Build a small update bridge and the full signed offline collection."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

from build_app_feed import apk_metadata
from prepare_models138 import sha

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'build/models138/apks'
CERT='2f0a0908f269bc039311edb58fca8863347f1e4c3a7cfaddd909991cf1f0b509'

def build(path,*tasks):
    subprocess.run(['bash','./gradlew',*tasks,'--no-daemon','--max-workers=2',
        '-PciSigningKeystore='+os.environ['CI_SIGNING_KEYSTORE']],cwd=path,check=True,timeout=2400)

def main():
    request=json.loads((ROOT/'docs/releases/app-0.3.138-inputs.json').read_text())
    OUT.mkdir(parents=True,exist_ok=True)
    bridge=ROOT/'build/bridge138'
    subprocess.run(['git','worktree','add','--detach',str(bridge),request['baselineSourceCommit']],check=True,cwd=ROOT)
    for name in ['RemoteAppSource.kt','RemoteFiles.java']:
        relative=Path('app/src/main/java/ru/dlyasvoih/app/data/update')/name
        shutil.copy2(ROOT/relative,bridge/relative)
    p=bridge/'app/build.gradle.kts'
    p.write_text(p.read_text().replace('versionCode = 141','versionCode = 142').replace('"0.3.137"','"0.3.138"'))
    sdk=Path(os.environ['ANDROID_HOME'])
    for project in [ROOT,bridge]:
        (project/'local.properties').write_text('sdk.dir='+str(sdk)+'\n')
    build(bridge,':app:assembleRelease')
    small=OUT/'DLYA_SVOIH_v0.3.138_Update_Helper.apk'
    shutil.copy2(bridge/'app/build/outputs/apk/release/app-release.apk',small)
    subprocess.run(['git','worktree','remove','--force',str(bridge)],check=True,cwd=ROOT)
    subprocess.run([sys.executable,str(ROOT/'tools/prepare_models138.py')],check=True)
    subprocess.run([sys.executable,'-m','unittest','discover','-s','tools','-p','test_model_collection138.py'],check=True,cwd=ROOT)
    build(ROOT,':app:testDebugUnitTest',':app:assembleDebug',':app:assembleDebugAndroidTest',':app:assembleRelease')
    for source,dest in [('debug/app-debug.apk','debug.apk'),('androidTest/debug/app-debug-androidTest.apk','test.apk'),
        ('release/app-release.apk','DLYA_SVOIH_v0.3.138.apk')]:
        shutil.copy2(ROOT/'app/build/outputs/apk'/source,OUT/dest)
    summary={'candidateSourceCommit':os.environ['GITHUB_SHA'],'workflowRunId':int(os.environ['GITHUB_RUN_ID']),
        'modelCount':615,'contentVersion':197,'originalGlbBytesPreserved':True,'status':'Android and visual review pending'}
    for path,code,key in [(OUT/'DLYA_SVOIH_v0.3.138.apk',143,'full'),(small,142,'bridge')]:
        meta=apk_metadata(path)
        assert meta['versionName']=='0.3.138' and meta['versionCode']==code and meta['packageName']=='ru.dlyasvoih.app'
        assert meta['signerSha256']==CERT
        meta.update(apkSha256=sha(path),apkBytes=path.stat().st_size,filename=path.name)
        assert meta['apkBytes'] <= (2*1024**3 if code==143 else 256*1024**2)
        with zipfile.ZipFile(path) as z:
            models=json.loads(z.read('assets/viewer3d/models.json'))['models']
            assert len(models)==(615 if code==143 else 19)
            for m in models:
                assert hashlib.sha256(z.read('assets/viewer3d/'+m['file'])).hexdigest()==m['packagedSha256'],m['id']
            assert hashlib.sha256(z.read('assets/database/guide-v29.db')).hexdigest()==request['databaseSha256']
        summary[key]=meta
    (OUT/'build-result.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary),flush=True)

if __name__=='__main__':main()
