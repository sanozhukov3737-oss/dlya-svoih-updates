"""Apply the reviewed, factual-scope-preserving catalog 195 -> 196 correction.

Requires the exact recovered public catalog. Does not import private photo research.
"""
import copy
import hashlib
import json
from pathlib import Path

from build_catalog import ROOT, ASSETS, validate

BASE_SHA256 = '7bffb7dfcd684958a3a183b4d49f4e4a7f11f6d4769d4fefa3ba5ba39560430a'
REPORT = ROOT / 'research/catalog-quality-196'
REMOVED_ID = 'pptx-v166-tm-124'
CANONICAL_ID = 'eng-pdf-v7-119'
REMOVED_MAP = {REMOVED_ID: CANONICAL_ID,
               'ordnance-v27-m430a1-hedp': 'ordnance-v29-ga-0128'}
TABLE_CARDS = ['atgm-9k111-fagot', 'atgm-konkurs-9m113',
               'ordnance-v29-ga-0299', 'ordnance-v29-ga-0300', 'ordnance-v29-ga-0301']
VARIANTS = {
    'ordnance-v29-ga-0543': ['SAPHEI', 'HEI', 'C-UAV / HE-AB', 'TP'],
    'ordnance-v29-ga-0546': ['APFSDS-T', 'GPR-PD-T', 'GPR-AB-T', 'A3B', 'TP-T', 'TPRR-T'],
    'ordnance-v29-ga-0547': ['HE-PD', 'HE-PROX', 'HE-PF-IM6-OES', 'HE-PFF-IM84',
                            'SAPIM345', 'TP / TP-T', 'FNF'],
}
TITLES = {
    'mine-audit-v25-us-m26': 'M26 — противопехотная мина',
    'ordnance-v29-ga-0172': 'M26 — ручная осколочная граната',
    'mine-audit-v25-us-m23': 'M23 — химическая мина',
    'ordnance-v29-ga-0152': 'M23 — винтовочная сигнальная граната',
    'ordnance-v29-ga-0191': 'M69 — учебная ручная граната',
    'ordnance-v29-ga-0400': 'M69 — проект учебного аналога M66',
}


def format_tables(body):
    """Preserve every cell, presenting wider tables in the reader's two columns."""
    blocks = body.split('\n\n')
    changed = 0
    for i, block in enumerate(blocks):
        if not block.startswith('|'):
            continue
        rows = [[cell.strip() for cell in line.strip().strip('|').split('|')]
                for line in block.splitlines()]
        if len(rows[0]) <= 2:
            continue
        headers = rows[0]
        assert all(len(row) == len(headers) for row in rows)
        formatted = [f'| {headers[0]} | Сведения |', '| --- | --- |']
        for row in rows[2:]:
            value = '; '.join(f'{label}: {text}' for label, text in zip(headers[1:], row[1:]))
            formatted.append(f'| {row[0]} | {value} |')
        blocks[i] = '\n'.join(formatted)
        changed += 1
    assert changed == 1
    return '\n\n'.join(blocks)


def revise(original):
    assert original['contentVersion'] == 195
    data = copy.deepcopy(original)
    cards = {c['id']: c for c in data['cards']}
    actions = []
    filler = ', указанный в переводном справочнике боеприпасов для БПЛА'
    handbook = [c for c in data['cards'] if filler in c['body']]
    assert len(handbook) == 177
    for card in handbook:
        card['body'] = card['body'].replace(filler, '').replace(
            '## Обозначение\n\nОбозначение в таблице:',
            '## Примечания к источнику\n\nОбозначение в исходной таблице:')
        card['summary'] = card['summary'].replace(filler, '')
    actions.append(dict(kind='handbook-copy-edit', cardIds=[c['id'] for c in handbook],
                        detail='Removed boilerplate and moved repeated source designations into reader notes. Source-only status, provenance and all product claims retained.'))

    for cid in TABLE_CARDS:
        cards[cid]['body'] = format_tables(cards[cid]['body'])
    actions.append(dict(kind='reader-table-format', cardIds=TABLE_CARDS))
    for cid, labels in VARIANTS.items():
        blocks = cards[cid]['body'].split('\n\n')
        positions = [i for i, b in enumerate(blocks) if b.startswith('|')]
        assert len(positions) == len(labels)
        for i, label in zip(positions, labels):
            blocks[i] = f'## {label}\n\n' + blocks[i]
        cards[cid]['body'] = '\n\n'.join(b for b in blocks if b != '## Характеристики')
    actions.append(dict(kind='manufacturer-variant-headings', cardIds=list(VARIANTS),
        sources=['https://knds.com/en/products/ammunition/30x113-mm-b',
                 'https://knds.com/en/products/ammunition/40-mm-cta',
                 'https://knds.com/en/products/ammunition/76-mm-l62-naval']))
    for cid, title in TITLES.items():
        old_title = cards[cid]['title']
        cards[cid]['title'] = title
        if old_title not in cards[cid]['tags']:
            cards[cid]['tags'].append(old_title)
    actions.append(dict(kind='disambiguate-different-models', cardIds=list(TITLES)))

    canonical, duplicate = cards[CANONICAL_ID], cards[REMOVED_ID]
    assert canonical['title'] == duplicate['title'] == 'ТМ-124'
    assert canonical['countries'] == duplicate['countries'] == ['ua']
    # New relationship IDs avoid collisions when an older saved card is archived
    # and retained by the production updater. Reuse already-public media paths.
    extra = copy.deepcopy(duplicate['images'][0])
    extra.update(id='quality196-tm124-presentation', position=1)
    canonical['images'].append(extra)
    source = copy.deepcopy(duplicate['sources'][0])
    source['id'] = 'quality196-tm124-presentation-source'
    canonical['sources'].append(source)
    limitations = duplicate['body'].split('## Источник и ограничения\n\n', 1)[1].strip()
    canonical['body'] += '\n## Примечания к источнику\n\n' + limitations + '\n'
    data['cards'] = [c for c in data['cards'] if c['id'] != REMOVED_ID]
    actions.append(dict(kind='merge-duplicate', removedId=REMOVED_ID, canonicalId=CANONICAL_ID,
        detail='Preserved both published images and document citations. Saved withdrawn cards remain archived and accessible under the existing ContentUpdater policy.'))

    old_m430 = cards['ordnance-v27-m430a1-hedp']
    m430 = cards['ordnance-v29-ga-0128']
    assert old_m430['countries'] == m430['countries'] == ['us']
    assert hashlib.sha256((ASSETS / old_m430['images'][0]['localPath']).read_bytes()).digest() == \
           hashlib.sha256((ASSETS / m430['images'][0]['localPath']).read_bytes()).digest()
    m430['title'] = 'M430A1 HEDP'
    m430['tags'] = list(dict.fromkeys(m430['tags'] + old_m430['tags']))
    for i, source in enumerate(old_m430['sources']):
        source = copy.deepcopy(source)
        source['id'] = f'quality196-m430a1-source-{i}'
        m430['sources'].append(source)
    # Keep the older document wording and unit presentation available, while
    # showing one article and one copy of the already identical illustration.
    m430['body'] += ('\n## Служебные сведения\n\n'
        'Архив объединённой записи M430A1 HEDP; исходные формулировки сохранены.\n\n' + old_m430['body'])
    data['cards'] = [c for c in data['cards'] if c['id'] not in REMOVED_MAP]
    actions.append(dict(kind='merge-duplicate', removedId=old_m430['id'], canonicalId=m430['id'],
        detail='Same US model, dimensions, mass, filling and identical exterior image. Retained all document citations and archived original wording.'))

    # The 40-mm signal round and the 105-mm HEAT round share an index, not a
    # silhouette. The Army sheet on PDF 606 explicitly names all three signals.
    m662 = cards['ordnance-v29-ga-0135']
    family = cards['ordnance-v29-ga-0132']['images'][0]
    for field in ('localPath', 'thumbnailPath', 'width', 'height'):
        m662['images'][0][field] = family[field]
    m662['images'][0]['caption'] = ('40-мм M662: общий наружный рисунок M583A1 / M661 / M662 из '
        'TM 43-0001-28, печатная с. 6-35, PDF 606. Источник прямо перечисляет три исполнения; '
        'рисунок не показывает различия цветов сигнала. Армия США; общественное достояние США. Не фотография.')
    m662['thumbnailPath'] = family['thumbnailPath']
    for source in m662['sources']:
        if source['id'].startswith('exterior-190-'):
            source['title'] = ('Архив прежней ошибочной привязки: TM 43-0001-28, PDF 234 '
                'показывает 105-мм M662, а не 40-мм сигнальный M662; иллюстрация заменена')
    m662['sources'].append(dict(id='quality196-m662-figure',
        title='Армия США — TM 43-0001-28, печатная с. 6-35, PDF 606: M583A1 / M661 / M662',
        url='https://www.bulletpicker.com/pdf/TM-43-0001-28-1994.pdf', accessedAt='2026-10-20'))
    actions.append(dict(kind='correct-document-illustrations', cardIds=[m662['id']]))

    illustrations = json.loads((REPORT / 'illustrations.json').read_text())
    for figure in illustrations['figures']:
        card = cards[figure['cardId']]
        picture = card['images'][0]
        for field in ('localPath', 'thumbnailPath', 'width', 'height'):
            picture[field] = figure[field]
        for field, checksum in [('localPath', 'sha256'), ('thumbnailPath', 'thumbnailSha256')]:
            assert hashlib.sha256((ASSETS / figure[field]).read_bytes()).hexdigest() == figure[checksum]
        picture['caption'] = (f"Документальный рисунок, не фотография: {figure['label']}. "
            f"Армия США, TM 43-0001-28, печатная с. {figure['printedPage']}, лист PDF {figure['pdfPage']}. "
            'Извлечён только внешний вид; схема разреза и текст страницы исключены. Общественное достояние США.')
        card['thumbnailPath'] = figure['thumbnailPath']
        card['sources'].append(dict(id=card['id'] + '-quality196-figure',
            title=f"Армия США — TM 43-0001-28, печатная с. {figure['printedPage']}, PDF {figure['pdfPage']}: внешний вид",
            url=illustrations['source'], accessedAt='2026-10-20'))
    actions.append(dict(kind='correct-document-illustrations',
                        cardIds=[f['cardId'] for f in illustrations['figures']]))
    withdrawn_pictures = ['ordnance-v29-ga-0223', 'ordnance-v29-ga-0492', 'ordnance-v29-ga-0193']
    for cid in withdrawn_pictures:
        card = cards[cid]
        card['images'] = []
        card['thumbnailPath'] = None
        for source in card['sources']:
            if cid == 'ordnance-v29-ga-0193' and source['id'].startswith('exterior-190-'):
                source['title'] = ('Архив прежней ошибочной привязки: TM 43-0001-29, PDF 65; '
                    'изображение не подтверждает учебную Mk 1A1 и удалено')
        card['body'] += ('\n## Примечания к источнику\n\n'
            'Ранее привязанная страница справочника не показывала внешний вид этой модели; '
            'ошибочная иллюстрация удалена.\n')
    actions.append(dict(kind='withdraw-non-illustrations',
                        cardIds=withdrawn_pictures,
                        detail='Compatibility table, packaging data and illustration of a different grenade are not exact exterior illustrations. No substitute model is presented as exact.'))
    before = {c['id']: c for c in original['cards']}
    changed = []
    for card in data['cards']:
        assert card['rowid'] == before[card['id']]['rowid']
        if card != before[card['id']]:
            card['searchProjection'] = 'reader'
            changed.append(card['id'])
    data['contentVersion'] = 196
    validate(data)
    return data, dict(fromVersion=195, contentVersion=196, changedCards=changed,
        removedIds=list(REMOVED_MAP), counts=dict(cards=len(data['cards']),
        images=sum(len(c['images']) for c in data['cards'])), actions=actions)


def main():
    path = ROOT / 'content/catalog.json'
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != BASE_SHA256:
        raise SystemExit('Expected the exact public catalog 195; no files changed.')
    original = json.loads(raw)
    data, report = revise(original)
    REPORT.mkdir(parents=True, exist_ok=True)
    # Small fixtures are sufficient to exercise real Android withdrawal behavior.
    (REPORT / 'withdrawn-card.json').write_text(json.dumps(
        next(c for c in original['cards'] if c['id'] == REMOVED_ID), ensure_ascii=False, indent=2) + '\n')
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    report['sourceSha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    (REPORT / 'changes.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(dict(changedCards=len(report['changedCards']), **report['counts']), ensure_ascii=False))


if __name__ == '__main__':
    main()
