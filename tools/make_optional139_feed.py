"""Prepare the small APK update only after the exact Android upgrade checks pass."""
import argparse
import hashlib
import json
from pathlib import Path
from build_app_feed import validate_catalog_feed

ROOT=Path(__file__).resolve().parents[1]
CERT='2f0a0908f269bc039311edb58fca8863347f1e4c3a7cfaddd909991cf1f0b509'
CHANGES=('3D-модели теперь скачиваются отдельно по желанию. Коллекцию из 615 моделей можно удалить '
    'и скачать снова, сохранив карточки, фотографии и избранное. Добавлены фоновые уведомления '
    'о новых версиях приложения и каталога с выключателем и защитой от повторов. '
    'После установки этой версии модели из прежнего большого APK заменяются необязательным пакетом; '
    'он не скачивается автоматически.')

def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--apks',type=Path,required=True);p.add_argument('--proof26',type=Path,required=True)
    p.add_argument('--proof36',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    build=json.loads((a.apks/'build-result.json').read_text())
    assert build['versionCode']==144 and build['versionName']=='0.3.139' and build['bundledModels']==0
    proofs=[]
    for path in [a.proof26,a.proof36]:
        result=json.loads(path.read_text());assert result['passed'] and result['sourceCommit']==build['sourceCommit']
        assert all(result['checks'].values())
        assert result['model-pack-result.json']['allModelBytesVerified']==615
        assert result['notification-result.json']['tapOpensUpdates']
        if result['api']==36:assert result['model-pack-result.json']['realDownload']
        proofs.append(result)
    assert {r['api'] for r in proofs}=={26,36}
    apk=a.apks/'DLYA_SVOIH_v0.3.139.apk';meta=build[apk.name]
    assert apk.stat().st_size==meta['bytes'] and sha(apk)==meta['sha256'] and meta['bytes']<256*1024**2
    original=json.loads((ROOT/'docs/releases/app-0.3.138-feed.json').read_text())
    feed=dict(original);feed.pop('appLarge',None)
    feed['app']={'formatVersion':1,'versionName':'0.3.139','versionCode':144,'packageName':'ru.dlyasvoih.app',
        'minSdk':26,'url':'https://github.com/sanozhukov3737-oss/dlya-svoih-updates/releases/download/app-0.3.139/'+apk.name,
        'bytes':meta['bytes'],'sha256':meta['sha256'],'signerSha256':CERT,'changes':CHANGES}
    validate_catalog_feed(feed)
    assert {k:v for k,v in feed.items() if k!='app'}=={k:v for k,v in original.items() if k not in ['app','appLarge']}
    payload=json.dumps(feed,ensure_ascii=False,indent=2)+'\n';assert len(payload.encode())<65536
    (a.out/'latest.json').write_text(payload)
    report={'status':'passed','build':build,'android':proofs,'pack':{k:v for k,v in
        json.loads((ROOT/'content/model-pack-1.json').read_text()).items() if k!='files'},
        'signerSha256':CERT,'feedSha256':hashlib.sha256(payload.encode()).hexdigest(),
        'catalogOfferUnchanged':True,'physicalPhoneTested':False,
        'notificationQa':'Future app/catalog offers exist only on disposable test emulators. The host taps the real notification after instrumentation exits and verifies the update screen.',
        'visualModelPayload':'All 615 GLBs are byte-identical to the reviewed 0.3.138 collection; new Android checks exercise external storage and the unchanged viewer.'}
    (a.out/'DLYA_SVOIH_0.3.139_Verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'apkBytes':meta['bytes'],'apkSha256':meta['sha256'],'feedSha256':report['feedSha256']}))

if __name__=='__main__':main()
