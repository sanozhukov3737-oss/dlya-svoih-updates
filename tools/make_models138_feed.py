"""Prepare a backward-compatible offer for the two verified signed APKs."""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request

from build_app_feed import validate_catalog_feed

REPO='sanozhukov3737-oss/dlya-svoih-updates'
CERT='2f0a0908f269bc039311edb58fca8863347f1e4c3a7cfaddd909991cf1f0b509'
FULL_CHANGES=('615 офлайн-3D-моделей: прежние 19 и 596 дополнительных. Поиск в коллекции, '
    'выбор вариантов и раскрываемые сведения об авторах и источниках. Связи с 511 карточками; '
    '44 спорных визуала остаются в общей коллекции с оговорками. Каталог 197 и сохранённые данные сохраняются.')
BRIDGE_CHANGES=('Подготовка к установке полной коллекции из 615 моделей. Это небольшой переходный выпуск. '
    'После установки откройте «Обновления» и ещё раз проверьте приложение, чтобы скачать полный выпуск. '
    'Прежние модели и сохранённые данные сохраняются.')

def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--apks',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    build=json.loads((a.apks/'build-result.json').read_text())
    with urllib.request.urlopen(f'https://github.com/{REPO}/releases/download/app-0.3.137/latest.json',timeout=60) as r:
        original=r.read(65537)
    assert len(original)<=65536
    root=validate_catalog_feed(json.loads(original))
    assert root['contentVersion']==197 and root['app']['versionCode']==141
    def offer(kind,code,changes):
        m=build[kind];path=a.apks/m['filename']
        assert m['versionName']=='0.3.138' and m['versionCode']==code and m['signerSha256']==CERT
        assert m['packageName']=='ru.dlyasvoih.app' and m['minSdk']==26
        assert path.stat().st_size==m['apkBytes'] and sha(path)==m['apkSha256']
        return {'formatVersion':1,'versionName':'0.3.138','versionCode':code,'packageName':m['packageName'],
            'minSdk':26,'url':f'https://github.com/{REPO}/releases/download/app-0.3.138/{path.name}',
            'bytes':m['apkBytes'],'sha256':m['apkSha256'],'signerSha256':CERT,'changes':changes}
    root['app']=offer('bridge',142,BRIDGE_CHANGES)
    root['appLarge']=offer('full',143,FULL_CHANGES)
    assert root['app']['bytes']<=256*1024**2 and root['appLarge']['bytes']<=2*1024**3
    validate_catalog_feed(root)
    encoded=json.dumps(root,ensure_ascii=False,indent=2)+'\n';assert len(encoded.encode())<=65536
    (a.out/'latest.json').write_text(encoded)
    (a.out/'publication-input.json').write_text(json.dumps({'sourceCommit':build['candidateSourceCommit'],
        'buildRunId':build['workflowRunId'],'apkSha256':root['appLarge']['sha256'],
        'bridgeSha256':root['app']['sha256'],'feedSha256':hashlib.sha256(encoded.encode()).hexdigest(),
        'status':'Prepared; publication still requires Android evidence and visual review'},indent=2)+'\n')
    (a.out/'notes.md').write_text(FULL_CHANGES+'\n\nПолный APK можно установить сразу поверх 0.3.137. '
        'Для старого встроенного загрузчика предусмотрен переходный APK: после него нужна повторная проверка обновления.\n')
    print(json.dumps({'feedBytes':len(encoded.encode()),'fullBytes':root['appLarge']['bytes'],
        'bridgeBytes':root['app']['bytes'],'status':'prepared, unpublished'}))

if __name__=='__main__':main()
