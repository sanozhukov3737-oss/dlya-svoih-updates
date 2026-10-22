#!/usr/bin/env python3
"""Prepare only a disposable debug checkout for the approved PMN visual check."""
import hashlib,json,runpy,shutil,subprocess
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
BASE='aaf393463cebe04e179487036165ac856c23886e'
MODEL_SHA='5875ba897efc6e62512238edb9b210705940e782fc8a37688fb1dbc72dd106fa'
PROTECTED=[
 'app/src/main/assets/viewer3d/index.html',
 'app/src/main/assets/viewer3d/viewer.bundle.js',
 'app/src/main/java/ru/dlyasvoih/app/ui/screens/OfflineModelViewer.kt',
 'app/src/main/java/ru/dlyasvoih/app/ui/screens/OfflineModels.kt',
]

def digest(data): return hashlib.sha256(data).hexdigest()

def main():
    report={'kind':'isolated unpublished debug model check','baseSource':BASE,
      'sourceCommit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
      'package':'ru.dlyasvoih.app.pmnvisualcheck','productionViewerFiles':{}}
    for name in PROTECTED:
        original=subprocess.check_output(['git','show',BASE+':'+name],cwd=ROOT)
        assert (ROOT/name).read_bytes()==original,'Production viewer differs: '+name
        report['productionViewerFiles'][name]=digest(original)
    generator=runpy.run_path(str(HERE/'build_pmn.py'))
    generator['build']()
    generated=HERE/'deliverables/pmn-visual-prototype.glb'
    assert digest(generated.read_bytes())==MODEL_SHA,'Generated PMN differs from the approved model'
    assets=ROOT/'app/src/main/assets/viewer3d'
    shutil.copyfile(generated,assets/generated.name)
    info=json.loads((HERE/'deliverables/model-metadata.json').read_text())
    entry={k:info[k] for k in ['id','file','author','license','licenseUrl','displayColorMode','displayNote','bytes']}
    entry.update(title='ПМН',subtitle='Пробная реконструкция · внешний вид',cardIds=[],
      source=info['referencePhotos'][0]['url'],packagedSha256=MODEL_SHA)
    manifest=assets/'models.json'
    original=manifest.read_bytes(); report['originalModelsJsonSha256']=digest(original)
    data=json.loads(original);assert not any(x['id']==entry['id'] for x in data['models'])
    data['models'].append(entry)
    manifest.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    gradle=ROOT/'app/build.gradle.kts'; text=gradle.read_text()
    assert text.count('buildTypes {')==1
    gradle.write_text(text.replace('buildTypes {','buildTypes {\n        getByName("debug") { applicationIdSuffix = ".pmnvisualcheck"; versionNameSuffix = "-pmn-visual-check" }',1))
    target=ROOT/'app/src/androidTest/java/ru/dlyasvoih/app/ui/screens/PmnVisualCheckTest.kt'
    assert not target.exists();shutil.copyfile(HERE/'PmnVisualCheckTest.kt',target)
    for name in PROTECTED:
        assert digest((ROOT/name).read_bytes())==report['productionViewerFiles'][name]
    report.update(modelSha256=MODEL_SHA,modelBytes=generated.stat().st_size,modelCardIds=[],
      modelGeneratedFromApprovedSource=True,modifiedViewerJavascript=False,releasePublished=False)
    out=ROOT/'build/pmn-android/apks';out.mkdir(parents=True,exist_ok=True)
    (out/'source-manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    shutil.copyfile(generated,out/generated.name)
    shutil.copyfile(HERE/'deliverables/model-metadata.json',out/'model-metadata.json')
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__': main()
