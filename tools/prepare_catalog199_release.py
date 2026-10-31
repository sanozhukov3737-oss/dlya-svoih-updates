"""Preserve the live APK offer while describing the verified saved ZIP."""
import argparse
import json
from pathlib import Path
from build_update_feed import write_feed
from restore_catalog199_candidate import EXPECTED_SHA256

CHANGES = ('Каталог №199: 2855 карточек и 2403 изображения. '
    'Добавлены 86 изображений для 78 карточек и 127 ссылок на источники. '
    'Прежние карточки, тексты, статусы и постоянные идентификаторы сохранены. '
    '23 отложенных изображения в обновление не включены. '
    'Приложение 0.3.139 и пакет 3D-моделей не менялись.')

def prepare(output, previous_feed):
    previous = json.loads(previous_feed.read_text())
    assert previous['contentVersion'] == 198, 'Publication baseline changed'
    feed = write_feed(output/'catalog-199.zip',
        'https://github.com/sanozhukov3737-oss/dlya-svoih-updates/releases/download/catalog-199/catalog-199.zip',
        output/'latest.json',CHANGES,previous['minAppCode'],previous_feed)
    assert feed['contentVersion'] == 199 and feed['sha256'] == EXPECTED_SHA256
    assert feed['app'] == previous['app']
    (output/'notes.txt').write_text(CHANGES+'\n\nУстановка: в приложении откройте «Обновления» и проверьте обновление каталога.\n')
    print(json.dumps(dict(contentVersion=199,unchangedApkOffer=True,sha256=feed['sha256'])))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--previous-feed',type=Path,required=True)
    args=parser.parse_args(); prepare(args.output,args.previous_feed)
