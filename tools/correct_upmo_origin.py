"""Apply the owner's UPM-O origin correction without replacing the published catalog."""
import argparse
import json
from pathlib import Path
import sqlite3
import unicodedata

CARD_ID = 'eng-pdf-v7-116'
CORRECTED_VERSION = 191
SUMMARY = ('УПМ-О — российская противопехотная осколочная мина. Известный образец имеет '
           'вытянутый цилиндрический корпус с крышкой и удлинённой нижней опорой. '
           'На фотографии показан тёмный корпус с выраженной фактурой поверхности.')
DESCRIPTION = ('УПМ-О относится к противопехотным осколочным минам. На известной внешней '
               'фотографии видны цилиндрический корпус с крышкой и длинная нижняя опора. '
               'По этим общим чертам образец отличается от низких круглых мин.\n\n'
               'Конкретный изготовитель и дата начала производства в проверенных материалах '
               'не установлены. Сходство с другими образцами само по себе не подтверждает '
               'общего производителя или принадлежности к одному семейству.')
SAFETY = ('Внешний вид не подтверждает безопасность предмета. Остановитесь, не приближайтесь, '
          'не трогайте и не перемещайте его. Предупредите окружающих и сообщите местным '
          'экстренным службам. При подозрении на мину оставайтесь на месте до помощи специалистов.')
BODY = ('## Страна и происхождение\n\nРоссия\n\n## Описание\n\n' + DESCRIPTION +
        '\n\n## При обнаружении\n\n' + SAFETY)
SOURCE = dict(id='upmo-nvp73-exterior-20261019',
              title='НВП73 — «УПМ-О или старая мина на новый лад» (внешний вид и класс)',
              url='https://t.me/nvp_73/4404', accessedAt='2026-10-19')


def normalized(value):
    return unicodedata.normalize('NFKC', value).lower().replace('ё', 'е')


def correct_catalog(path):
    path = Path(path)
    data = json.loads(path.read_text(encoding='utf-8'))
    cards = [c for c in data['cards'] if c['id'] == CARD_ID]
    if len(cards) != 1 or cards[0]['countries'] not in (['ua'], ['ru']):
        raise ValueError('Unexpected UPM-O catalog record')
    card = cards[0]
    card.update(countries=['ru'], summary=SUMMARY, body=BODY)
    if not any(s['id'] == SOURCE['id'] for s in card['sources']):
        card['sources'].append(dict(SOURCE))
    # Bundled JSON version remains unchanged: published catalog 190 is corrected separately.
    # Do not upgrade sourceGrade or verifiedAt: origin comes from the owner's correction.
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return data['contentVersion']


def correct_database(path):
    if sqlite3.sqlite_version_info > (3, 45, 1):
        raise RuntimeError('Production database writes require SQLite 3.45.1 or older')
    with sqlite3.connect(path) as db:
        db.row_factory = sqlite3.Row
        version = int(db.execute("SELECT value FROM metadata WHERE key='content_version'").fetchone()[0])
        card = db.execute('SELECT * FROM cards WHERE id=?', (CARD_ID,)).fetchone()
        countries = [row[0] for row in db.execute('SELECT countryId FROM card_countries WHERE cardId=?', (CARD_ID,))]
        if version not in (188, 190, CORRECTED_VERSION) or card is None or countries not in (['ua'], ['ru']):
            raise ValueError('Expected source catalog 188, published catalog 190 or corrected catalog 191')
        corrected_version = CORRECTED_VERSION if version >= 190 else version
        search = normalized(' '.join([card['title'], SUMMARY, BODY, card['tags'].replace(' · ', ' ')]))
        db.execute('UPDATE cards SET summary=?,body=?,searchText=? WHERE id=?', (SUMMARY, BODY, search, CARD_ID))
        db.execute('DELETE FROM card_countries WHERE cardId=?', (CARD_ID,))
        db.execute('INSERT INTO card_countries VALUES (?,?)', (CARD_ID, 'ru'))
        db.execute('INSERT OR REPLACE INTO sources VALUES (?,?,?,?,?)',
                   (SOURCE['id'], CARD_ID, SOURCE['title'], SOURCE['url'], SOURCE['accessedAt']))
        db.execute("UPDATE metadata SET value=? WHERE key='content_version'", (str(corrected_version),))
        db.execute("INSERT INTO cards_fts(cards_fts) VALUES ('rebuild')")
        db.execute("INSERT INTO cards_fts(cards_fts) VALUES ('integrity-check')")
        if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok' or db.execute('PRAGMA foreign_key_check').fetchall():
            raise ValueError('Corrected catalog failed integrity checks')
    return corrected_version


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--catalog', type=Path)
    parser.add_argument('--database', type=Path)
    args = parser.parse_args()
    if not (args.catalog or args.database):
        parser.error('Specify --catalog and/or --database')
    result = {}
    if args.catalog:
        result['sourceVersion'] = correct_catalog(args.catalog)
    if args.database:
        result['databaseVersion'] = correct_database(args.database)
    print(json.dumps(dict(cardId=CARD_ID, country='ru', **result)))
