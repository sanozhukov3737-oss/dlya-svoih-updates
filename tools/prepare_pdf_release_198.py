"""Package the reviewed PDF snapshot, preserving the current APK offer."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile
from build_catalog import ROOT, ASSETS, validate
from build_pack import make_pack
from build_update_feed import write_feed


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare(request_path, previous_feed, output):
    request = json.loads(Path(request_path).read_text())
    previous = json.loads(Path(previous_feed).read_text())
    source = ROOT / 'content/catalog.json'
    database = ASSETS / 'database/guide-v29.db'
    data = json.loads(source.read_text())
    assert request['contentVersion'] == data['contentVersion'] == data['catalogVersion'] == 198
    assert sha(source) == request['catalogSha256']
    assert sha(database) == request['databaseSha256']
    assert previous['contentVersion'] < 198
    assert previous['app']['versionCode'] >= previous['minAppCode']
    assert len(data['cards']) == request['cards'] == 2855
    assert sum(len(c['images']) for c in data['cards']) == request['images'] == 2317
    validate(data)
    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)
    pack = out / 'catalog-198.zip'
    make_pack(source, pack)
    with zipfile.ZipFile(pack) as archive:
        assert hashlib.sha256(archive.read('guide.db')).hexdigest() == request['databaseSha256']
    feed = write_feed(pack,
        'https://github.com/sanozhukov3737-oss/dlya-svoih-updates/releases/download/catalog-198/catalog-198.zip',
        out / 'latest.json', request['changes'], previous['minAppCode'], previous_feed)
    assert feed['app'] == previous['app']
    result = dict(contentVersion=198, cards=2855, images=2317, bytes=feed['bytes'],
                  sha256=feed['sha256'], unchangedApkOffer=True,
                  catalogSha256=request['catalogSha256'], databaseSha256=request['databaseSha256'])
    (out / 'package-verification.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    (out / 'notes.txt').write_text(request['changes']+'\n\nУстановка: откройте в приложении раздел «Обновления» и проверьте обновление каталога.\n')
    print(json.dumps(result, ensure_ascii=False))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ('request', 'previous-feed', 'output'):
        parser.add_argument('--'+name, required=True)
    args = parser.parse_args()
    prepare(args.request, args.previous_feed, args.output)
