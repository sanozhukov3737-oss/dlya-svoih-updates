"""Verify the small signed APK and preserve exact build provenance."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]

def main():
    out=ROOT/'build/models139/apks';out.mkdir(parents=True,exist_ok=True)
    summary={'sourceCommit':os.environ['GITHUB_SHA'],'runId':int(os.environ['GITHUB_RUN_ID']),
        'versionName':'0.3.139','versionCode':144,'bundledModels':0,'optionalModels':615}
    sdk=Path(os.environ['ANDROID_HOME'])
    for src,dest in [('release/app-release.apk','DLYA_SVOIH_v0.3.139.apk'),('debug/app-debug.apk','debug.apk'),
        ('androidTest/debug/app-debug-androidTest.apk','test.apk')]:
        p=out/dest;shutil.copy2(ROOT/'app/build/outputs/apk'/src,p)
        signature=subprocess.run([str(sdk/'build-tools/36.0.0/apksigner'),'verify','--print-certs',str(p)],check=True,capture_output=True,text=True).stdout
        assert '2f0a0908f269bc039311edb58fca8863347f1e4c3a7cfaddd909991cf1f0b509' in signature
        print(signature,flush=True)
        if dest=='DLYA_SVOIH_v0.3.139.apk':
            for field,value in [('application-id','ru.dlyasvoih.app'),('version-code','144'),('version-name','0.3.139'),('min-sdk','26'),('debuggable','false')]:
                actual=subprocess.run([str(sdk/'cmdline-tools/latest/bin/apkanalyzer'),'manifest',field,str(p)],check=True,capture_output=True,text=True).stdout.strip()
                assert actual==value,(field,actual)
        with zipfile.ZipFile(p) as z:
            if dest!='test.apk':
                assert not any(n.endswith('.glb') for n in z.namelist())
                registry=z.read('assets/viewer3d/models.json')
                assert hashlib.sha256(registry).hexdigest()=='e62321912e9c8b3da7f77d09eaeadf5383dc9a1f259d7f22d10642f48e41daab'
                assert len(json.loads(registry)['models'])==615
                assert hashlib.sha256(z.read('assets/database/guide-v29.db')).hexdigest()=='a2cf495b7476e65a52d8f14b22fe737e812310c4c49ee4aa784afd27ab59e8b5'
                assert z.read('assets/viewer3d/pack.json')==(ROOT/'content/model-pack-1.json').read_bytes()
        with p.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
        summary[dest]={'bytes':p.stat().st_size,'sha256':digest}
    assert summary['DLYA_SVOIH_v0.3.139.apk']['bytes']<256*1024**2
    (out/'build-result.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary))

if __name__=='__main__':main()
