"""Apply the reviewed catalog 196 -> 197 editorial update to the exact public base.

No new images, specifications, operating procedures, model geometry or medical
content are introduced. Existing source-only records remain source-only.
"""
import copy
import hashlib
import json
from pathlib import Path

from build_catalog import ROOT, validate
from editorial_197_texts import APPEARANCE, DEFERRED, FAMILIES

BASE_SHA256 = '14f58a62c87666cf549858c0f894a68f2b7f3cc71106fc25a7a3ee2f938400b6'
REPORT = ROOT / 'research/catalog-review-197'
WITHDRAWN_IMAGE_CARD = 'ordnance-v27-p3-jumping-pakistan'
DATE = '2026-10-21'
EVIDENCE = {
    'adron': dict(title='АДРОН — история компании; год основания',
        url='https://adron.ua/about/'),
    'ivp': dict(title='Интервибухпром — собственное раскрытие сведений о регистрации',
        url='https://ivp.pat.ua/'),
    'innateks': dict(title='LB.ua — выступление основателя «Иннатекс», 13.10.2023',
        url='https://lb.ua/society/2023/10/13/578815_kozhen_viznaie_shcho_poli_boyu_zavzhdi.html'),
    'nasv': dict(title='НАСВ — материалы конференции 2024, PDF 241',
        url='https://asv.mil.gov.ua/sites/default/files/2025-03/1-zbirnyk-tez_2024_.pdf#page=241'),
    'ofsp2022': dict(title='Документ 2022 года — перечень ОФСП, PDF 5',
        url='https://sprotyvg7.com.ua/wp-content/uploads/2023/04/%D0%91%D0%9F%D0%9B%D0%90_1-2.pdf#page=5'),
    'ofsp2024': dict(title='ЦНИИ ВСУ — семинар 2024, печатная с. 142, PDF 143',
        url='https://crsi.mil.gov.ua/files/isps/isps-collection-2024.pdf#page=143'),
}


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def add_source(card, key):
    source = EVIDENCE[key]
    # Preserve prior citations and their IDs even if a second citation uses the
    # same document with a more precise page or a separate historical claim.
    card['sources'].append(dict(id=card['id'] + '-review197-' + key,
        title=source['title'], url=source['url'], accessedAt=DATE))


def append_note(card, text):
    if '## Примечания к источнику' not in card['body']:
        card['body'] = card['body'].rstrip() + '\n\n## Примечания к источнику\n'
    card['body'] = card['body'].rstrip() + '\n\n' + text + '\n'


def revise(original, review):
    assert original['contentVersion'] == 196
    data = copy.deepcopy(original)
    cards = {c['id']: c for c in data['cards']}
    before = {c['id']: c for c in original['cards']}
    short = review['shortArticles']
    assert len(short) == 158 and len(review['sharedImageGroups']) == 71
    families = {i: text for indices, text in FAMILIES for i in indices}
    no_photo_family = ('В переводном перечне этому изготовителю отнесены ПНИ-1, '
        'ПНУ-1-1/2 и ПНУ-1-36. Это три отдельных обозначения; точные наружные '
        'виды в использованном материале не представлены.')
    families.update({i: no_photo_family for i in (6, 7, 8)})
    assert set(families) | set(DEFERRED) == set(range(1, 159))
    decisions = []
    for i, row in enumerate(short, 1):
        card = cards[row['cardId']]
        assert card['title'] == row['title']
        entry = dict(index=i, cardId=card['id'], title=card['title'],
            beforeBodySha256=digest(card['body']), beforeCharacters=len(card['body']))
        if i in DEFERRED:
            entry.update(action='retain-brief', basis=DEFERRED[i], newEvidence=[])
            decisions.append(entry)
            continue
        evidence = []
        # The original source states the broad type. Replace its generic visual
        # sentence with an individually reviewed description of the existing art.
        if i <= 4:
            lead = card['title'] + ' — отдельный вариант серии ОФСП.'
            prior_notes = card['body'].split('## Обозначение\n\n', 1)[1].strip()
            origin = ''
        else:
            lead = card['body'].split('## Описание\n\n', 1)[1].split('\n\n', 1)[0].split('. ', 1)[0]
            if not lead.endswith('.'):
                lead += '.'
            origin = card['body'].split('## Происхождение\n\n', 1)[1].split('\n\n##', 1)[0]
            prior_notes = card['body'].split('## Примечания к источнику\n\n', 1)[1].strip()
        blocks = ['## Описание', lead]
        if i in APPEARANCE:
            blocks.extend(['## Внешний вид', APPEARANCE[i]])
        if i not in (5, 9, 10, 11, 37, 49, 70, 73, 124, 128, 131, 143):
            blocks.extend(['## Обозначения и варианты', families[i]])
        history = ''
        if i <= 4:
            history = ('Серия перечислена в документе, датированном 2022 годом. '
                'В докладе 2024 года авторы связывают начало её промышленного выпуска '
                'с маркировкой начала 2022 года. Конкретный изготовитель по этим материалам не установлен.')
            evidence = ['ofsp2022', 'ofsp2024']
        elif i in (6, 7, 8):
            history = ('Компания «Интервибухпром» указывает дату государственной регистрации '
                '17 мая 2001 года. Это дата регистрации организации, а не появления данной модели.')
            evidence = ['ivp']
        elif i in (9, 74, 75, 76):
            history = ('«АДРОН» основана в 1994 году выпускниками Киевского высшего военного '
                'авиационного инженерного училища. Компания работает в области защиты '
                'летательных аппаратов и авиационных боеприпасов.')
            evidence = ['adron']
            prior_notes += ('\n\nСайт компании подтверждает её историю, но не устанавливает '
                'дату разработки данного исполнения; обозначение модели сохранено по справочнику.')
        elif i in (10, 16, 18, 21, 24, 31):
            history = ('По выступлению основателя в 2023 году, прежним профилем «Иннатекс» '
                'был дереворежущий инструмент; боеприпасы для БПЛА фирма выпускает с 2022 года.')
            evidence = ['innateks']
            prior_notes += '\n\nУказанный год относится к профилю компании; дата появления этого исполнения не установлена.'
        elif i in (5, 12, 13, 14, 35, 36, 38, 39):
            history = 'Обозначение упоминается в материалах конференции НАСВ 2024 года.'
            evidence = ['nasv']
            prior_notes += '\n\nДата публикации не является датой принятия модели на вооружение.'
        if origin:
            blocks.extend(['## Происхождение', origin])
        if history:
            blocks.extend(['## Исторические сведения', history])
        blocks.extend(['## Примечания к источнику', prior_notes])
        card['body'] = '\n\n'.join(blocks) + '\n'
        card['summary'] = lead
        if i in APPEARANCE:
            card['summary'] += ' ' + APPEARANCE[i].split('. ', 1)[0].rstrip('.') + '.'
        for key in evidence:
            add_source(card, key)
        entry.update(action='expand-description', basis='Existing illustration and source nomenclature; independent historical context only where cited.',
            newEvidence=[EVIDENCE[key]['url'] for key in evidence])
        decisions.append(entry)

    caption_actions = []
    def caption(cid, text):
        card = cards[cid]
        assert len(card['images']) == 1
        image = card['images'][0]
        old = image['caption']
        image['caption'] = text
        assert old != text
        caption_actions.append(dict(cardId=cid, imageId=image['id'], before=old, after=text))

    # The picture explicitly identifies a different class/model. It adds no
    # trustworthy visual information to this card and has no confirmed family link.
    card = cards[WITHDRAWN_IMAGE_CARD]
    assert card['images'][0]['id'] == 'v40-p3-jumping-family-mk2'
    removed = copy.deepcopy(card['images'][0])
    card['images'] = []
    card['thumbnailPath'] = None
    append_note(card, 'Снимок противотанковой P3 Mk2 удалён: принадлежность к модели или семейству P3 Jumping не подтверждена.')
    for cid, suffix in [('mine-audit-v26-su-pmr-2m', 'М'), ('mine-audit-v26-su-pmr-2u', 'У')]:
        caption(cid, 'Музейный разрезной макет экспортной морской ПМР-2Э — семейный ориентир. '
            f'Закрытый наружный вид и исполнение с суффиксом {suffix} этим кадром не подтверждаются. '
            'С одноимённой югославской сухопутной PMR-2 не смешивать.')
    for cid, shown, family, page in [
        ('ordnance-v27-155-mm-m692-m731-adam', 'M731', 'M692 / M731 ADAM', 354),
        ('ordnance-v27-m718-m741-raam-155-mm-snaryady', 'M741', 'M718 / M741 RAAM', 358),
    ]:
        caption(cid, f'Документальный наружный рисунок {shown}, не фотография. '
            f'Армия США, TM 43-0001-28, PDF {page}: лист прямо называет {shown}. '
            f'В обзорной карточке {family} используется как пример одного исполнения; '
            'различия остальных вариантов не показаны. Общественное достояние США.')
    for cid in ['ordnance-v27-100-mm-at-mine-vetnam', 'ordnance-v27-150-mm-at-mine-vetnam', 'ordnance-v27-200-mm-at-mine-vetnam']:
        caption(cid, 'Сводный справочный рисунок вьетнамской линии 100/150/200 мм из TM 5-280 (1971). '
            'Это схематическая иллюстрация, а не фотография закрытого готового изделия. '
            'Отдельный размерный вариант данным общим рисунком не подтверждается.')
    for cid in ['ordnance-v29-ga-0018', 'ordnance-v29-ga-0019']:
        caption(cid, 'Общая иллюстрация из заводских листов Elbit Systems: '
            'производитель использует одинаковую фотографию для M920 и M950. '
            'Она не показывает различия двух исполнений. © Elbit Systems.')
    for cid in ['ordnance-v29-ga-0281', 'ordnance-v29-ga-0282']:
        caption(cid, 'Документальная иллюстрация обоих исполнений 81-мм M375A1 и M375A2; не фотография. '
            'Армия США, TM 43-0001-28, физическая страница PDF 464. '
            'В карточках сохранён общий фрагмент листа с двумя наружными видами. Общественное достояние США.')

    # Repeated pictures with different crops are not caught by byte-hash groups.
    family_indices = [*range(55,58), *range(60,63), *range(99,103),
        *range(116,124), *range(144,153)]
    for i in family_indices:
        cid = short[i-1]['cardId']
        old = cards[cid]['images'][0]['caption']
        caption(cid, old + ' Общая иллюстрация линии; отдельные наружные отличия данного исполнения по ней не подтверждены.')
    cid = short[42]['cardId']
    caption(cid, cards[cid]['images'][0]['caption'] +
        ' На корпусе читается «ЗК 2.7 ШОК», тогда как строка перечня названа «ШУТ». Точный вид ШУТ не подтверждён.')
    append_note(cards[cid], 'Расхождение источника: строка названа «ЗК 2.7 ШУТ», а на фотографии читается «ЗК 2.7 ШОК». Снимок сохранён только как ориентир линии; название карточки по нему не исправлялось.')
    cid = short[102]['cardId']
    caption(cid, cards[cid]['images'][0]['caption'] + ' На фотографии читается МОН-100 без суффикса .1; точное исполнение не подтверждено.')
    cid = short[70]['cardId']
    caption(cid, cards[cid]['images'][0]['caption'] + ' На корпусе написано «МАКЕТ»; показан демонстрационный образец.')
    for i in (153,154):
        cid = short[i-1]['cardId']
        caption(cid, cards[cid]['images'][0]['caption'] +
            ' Показаны отдельные образцы и упаковка; полного наружного вида собранной боевой части этот кадр не устанавливает.')

    for entry in decisions:
        card = cards[entry['cardId']]
        entry.update(afterBodySha256=digest(card['body']), afterCharacters=len(card['body']))
    changed = []
    for card in data['cards']:
        if card != before[card['id']]:
            card['searchProjection'] = 'reader'
            changed.append(card['id'])
    data['contentVersion'] = 197
    validate(data)
    assert sum(d['action'] == 'expand-description' for d in decisions) == 153
    return data, dict(baseContentVersion=196, contentVersion=197, changedCards=changed,
        expandedDescriptions=153, retainedBriefDescriptions=5,
        historicalContextCards=sum(bool(d['newEvidence']) for d in decisions),
        captionCorrections=caption_actions, withdrawnImage=dict(cardId=WITHDRAWN_IMAGE_CARD, image=removed),
        shortDecisions=decisions, counts=dict(cards=len(data['cards']),
            images=sum(len(c['images']) for c in data['cards']),
            sources=sum(len(c['sources']) for c in data['cards'])))


def main():
    path = ROOT / 'content/catalog.json'
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != BASE_SHA256:
        raise SystemExit('Expected exact public catalog 196; no files changed.')
    data, report = revise(json.loads(raw), json.loads((ROOT / 'research/catalog-quality-196/after.json').read_text()))
    REPORT.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    report['sourceSha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    (REPORT / 'changes.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('shortDecisions','captionCorrections','withdrawnImage','changedCards')},ensure_ascii=False))


if __name__ == '__main__':
    main()
