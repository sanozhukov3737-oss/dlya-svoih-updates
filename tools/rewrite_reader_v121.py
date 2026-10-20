"""Whole-catalog reader edit from an explicit catalog-150 input snapshot.

No dates, materials, dimensions, operational detail or model associations are
invented. Existing table values, evidence qualifiers and source records remain.
"""
from pathlib import Path
import argparse
import collections
import hashlib
import json
import re
from reader_121_curated import CURATED
from reader_121_style import polish, consolidate_materials, explanatory_context, CITATION
ROOT = Path(__file__).resolve().parents[1]
READY = {'eng-pmn','eng-pmn-2','ref-v8-pmn-3','ref-v8-pmn-4','eng-pfm-1','eng-ozm-72',
    'eng-mon-50','ref-v8-mon-90','eng-tm-62m','ref-v8-tm-57','ref-v8-tm-72',
    'mine-audit-v25-su-tm-83','eng-ptm-3','mine-audit-v25-su-ptm-1','ref-v8-pmd-6',
    'ref-v8-tm-62p3','grenade-f1-soviet','grenade-rgd-5','grenade-rgn','grenade-rgo'}
MEASURE = re.compile(r'(?:≈\s*)?\d+(?:[.,]\d+)?(?:\s*[–−-]\s*\d+(?:[.,]\d+)?)?\s*(?:кг|мм|см|мг|мкм|г|lb|lbs|in|cm|mm|kg|oz|м|m)\b',re.I)
REF_START = re.compile(r'\((?:James Madison University|Landmine Monitor(?: Report)?|Музей «Дорога памяти»|100 лучших товаров|НМЗ «Искра»|European Commission|JMU CISR|GICHD|U\.S\. Department|Naval EOD)[^\n()]*\)')
LABELS = {
    'Корпус':'Материал корпуса', 'Категория':'Класс', 'Размеры, мм':'Габариты, мм',
    'Размеры, м':'Габариты, м', 'Внешняя форма':'Форма корпуса',
    'Тип основного наполнения':'Основное вещество', 'Основное наполнение':'Основное вещество',
    'Наполнение':'Основное вещество', 'Масса наполнения':'Масса основного вещества',
    'Тип ВВ основного наполнения':'Тип основного ВВ', 'Масса ВВ основного наполнения':'Масса основного ВВ',
    'Масса основного наполнения':'Масса основного вещества',
    'Наполнение / материал':'Основное вещество / материал',
    'Масса отдельного наполнения':'Масса основного вещества / материала',
    'Наполнение снаряда (Projectile filling)':'Масса снаряжения снаряда',
    'Взрывчатое наполнение — NEQ':'Масса ВВ — NEQ',
}
FIXES = {
 'В описании описана':'В описании указана', 'в описании описана':'в описании указана',
 'В описании описаны':'В описании указаны', 'в описании описаны':'в описании указаны',
 'представляют собой разными исполнениями':'представляют собой разные исполнения',
 'Более поздний справочник немного другие значения':'В другой справочной записи приведены немного другие значения',
 'JMU CISR объединены':'В описании УЗРГМ объединены',
 'JMU CISR он представлен':'В справочном описании он представлен',
 'JMU CISR перечисляет':'Справочное описание перечисляет',
 'JMU CISR заголовок строки':'В справочной записи заголовок строки',
 'Характерная особенность — обтекаемую внешнюю форму':'Характерная особенность — обтекаемая внешняя форма',
 'Сам боеприпас и наружную пусковую трубу.':'Сам боеприпас и наружная пусковая труба — разные предметы.',
 'очертания округлого корпуса и рельефу':'очертаниям округлого корпуса и рельефу',
}
META_SENTENCE = re.compile(r'^(?:Для этой карточки найден |Для карточки выбран |В каталоге полезно хранить |Для поиска сохранено |Для поиска использовано |Проверены все |Проверенный источник краткий:|Источник новой сверки |Получен PDF|Первоначальная запись каталога |Новая сверка |Источник дополнения:|Сведения о наполнении:|Уточнение справочных данных:)')
BOILERPLATE = {
 'Названия сохранены как исторические обозначения происхождения, без переноса сведений об оборудовании и способах его применения.',
 'Название модели не позволяет судить о состоянии найденного предмета.',
 'Корпус с боевым опасным наполнением; точные внутренние части и состояние установленного изделия снаружи неизвестны.',
 'Массу и другие показатели соседних вариантов к этой модели не приравнивают.',
}


def split_sections(article):
    matches=list(re.finditer(r'^## (.+)$',article,re.M))
    if not matches:return [('',article.strip())]
    result=[]
    if article[:matches[0].start()].strip():result.append(('',article[:matches[0].start()].strip()))
    for i,m in enumerate(matches):
        end=matches[i+1].start() if i+1<len(matches) else len(article)
        result.append((m.group(1),article[m.end():end].strip()))
    return result


def paragraphs(text): return [p.strip() for p in re.split(r'\n\s*\n',text) if p.strip()]


def sentences(text):
    # Sentence boundaries exclude initials, decimal quantities and abbreviated units.
    return re.split(r'(?<=[.!?])\s+(?=[А-ЯЁA-Z«])',text.strip())


def clean(text,notes):
    # Value cells retain their exact original scope and evidence qualifiers.
    blocks=[]
    for p in paragraphs(text):
        if p.startswith('|') or p.startswith('### '):
            blocks.append(strip_table_citations(p,notes) if p.startswith('|') else p)
        else:
            blocks.append(clean_prose(p,notes))
    return '\n\n'.join(p for p in blocks if p)


def strip_table_citations(text,notes):
    def archive(m):
        if MEASURE.search(m[0]):return m[0]
        notes.append('Табличная ссылка: '+m[0]);return ''
    return REF_START.sub(archive,CITATION.sub(archive,text)).replace('  |',' |')


def clean_prose(text,notes):
    def remove_ref(m):
        if MEASURE.search(m[0]):return m[0]
        notes.append(m[0]);return ''
    text=REF_START.sub(remove_ref,text)
    for before,after in FIXES.items():text=text.replace(before,after)
    text=re.sub(r'Корпус изготовлен из материала:\s*([^.!?]+)[.!?]?',lambda m:'Материал корпуса — '+m[1].strip().lower()+'.',text)
    # Fix incomplete noun phrases without recasting uncertain evidence as fact.
    text=text.replace(' — противобортовая.',' — противобортовая мина.')
    text=text.replace(' — противотранспортная, дистанционная.',' — противотранспортная мина дистанционного класса.')
    text=re.sub(r'([^.\n]+) — противопехотная осколочная\.',r'\1 — противопехотная осколочная мина.',text)
    text=re.sub(r'([^.\n]+) — противопехотная\.',r'\1 — противопехотная мина.',text)
    text=re.sub(r'([^.\n]+) — противотанковая\.',r'\1 — противотанковая мина.',text)
    result=[]
    for p in paragraphs(text):
        if p.startswith('|') or p.startswith('### '):result.append(p);continue
        kept=[]
        for sentence in sentences(p):
            s=sentence.strip()
            if s in BOILERPLATE or (META_SENTENCE.search(s) and not MEASURE.search(s)):
                notes.append(s);continue
            s=re.sub(r'\s{2,}',' ',s).strip()
            if s:kept.append(s)
        if kept:result.append(' '.join(kept))
    return polish('\n\n'.join(result),notes)


def edit_labels(text):
    lines=[]
    for line in text.splitlines():
        m=re.fullmatch(r'\|\s*([^|]+?)\s*\|\s*([^|]*?)\s*\|',line)
        if m and m[1] in LABELS:
            line='| '+LABELS[m[1]]+' | '+m[2]+' |'
        elif m and m[1].startswith('Взрывчатое наполнение — NEQ,'):
            line='| '+m[1].replace('Взрывчатое наполнение','Масса ВВ',1)+' | '+m[2]+' |'
        lines.append(line)
    return '\n'.join(lines)


def table_blocks(article):
    tables=[]
    for p in paragraphs(article):
        if not p.startswith('|'):continue
        rows=[]
        for line in p.splitlines():
            m=re.fullmatch(r'\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|',line)
            if m and m[1] not in ('Параметр','Характеристика','---') and not re.fullmatch(r'[- :]+',m[1]): rows.append((m[1],m[2]))
        if rows:tables.append(rows)
    return tables


def named_intro(card,text):
    title=card['title'].split(' — ')[0].strip()
    # A bare classification becomes a proper model sentence; historical/event
    # statements and qualified source claims are left intact.
    if re.match(r'^(?:Советская|Российская|Китайская|Японская|Чилийская|Пакистанская|Аргентинская|Южноафриканская|Финская|Французская|Немецкая|Итальянская|Американская|Британская|Противопехотная|Противотанковая|Осколочная|Семейство|Промышленный)\b',text):
        if title.lower() not in text[:len(title)+40].lower():
            text=title+' — '+text[0].lower()+text[1:]
    return text


def enrich_from_existing_facts(card,desc,article):
    """Describe physical scale/identity only when the existing table is unambiguous."""
    ps=paragraphs(desc)
    # Consolidate standalone "X составляет" strings into one useful size paragraph.
    numerical=[]; others=[]
    for p in ps:
        ss=sentences(p)
        if ss and all(re.match(r'^(?:Полная масса|Общая масса|Масса изделия|Длина изделия|Диаметр|Высота|Ширина|Длина) составляет ',s) for s in ss):
            for s in ss:
                m=re.match(r'(.+?) составляет (.+?)[.]?$',s)
                if m:numerical.append((m[1],m[2].rstrip('.')))
        else:others.append(p)
    if numerical:
        # Preserve exact quantities and their original model/completeness qualifiers.
        ordered=list(dict.fromkeys(numerical))
        mass=[]; mass_values=set()
        for k,v in ordered:
            if 'масса' in k.lower() and v not in mass_values:
                mass.append((k,v));mass_values.add(v)
        size=[(k,v) for k,v in ordered if 'масса' not in k.lower()]
        phrases=[]
        if size:phrases.append('Справочные размеры: '+', '.join(k.lower()+' '+v for k,v in size)+'.')
        if mass:phrases.append(' '.join(k+' — '+v+'.' for k,v in mass))
        if phrases:others.append(' '.join(phrases))
    ps=consolidate_materials(others or ps)
    desc='\n\n'.join(ps)
    # Exact table cells are reused, never parsed from metadata or a neighboring model.
    tables=table_blocks(article)
    if len(desc.split())<70 and len(tables)==1 and not re.search(r'^### ',article,re.M):
        rows=dict(tables[0]); parts=[]
        material=rows.get('Материал корпуса')
        if material and len(material)<160 and not re.search(r'не (?:установлен|подтвержд|извест)|требует',material,re.I):
            if material.lower() not in desc.lower() and not re.search(r'корпус[^.]+(?:сталь|металл|пласт|чугун|дерев|бакелит)',desc,re.I):
                parts.append('Материал корпуса — '+material[0].lower()+material[1:]+'.')
        selected=[]
        for key in ('Диаметр корпуса','Диаметр','Длина изделия','Длина','Ширина','Высота корпуса','Высота','Высота без взрывателя','Длина со взрывателем'):
            val=rows.get(key)
            if val and len(val)<120 and MEASURE.search(val) and val not in desc and not re.search(r'не подтвержд|требует',val,re.I):
                selected.append((key,val))
                if len(selected)==3:break
        if selected:parts.append('Габариты в описанной комплектации: '+', '.join(k.lower()+' '+v for k,v in selected)+'.')
        for key in ('Полная масса','Общая масса','Полная масса мины','Масса всей мины','Масса изделия','Масса снаряда','Полная масса выстрела','Масса полного выстрела'):
            val=rows.get(key)
            if val and len(val)<130 and MEASURE.search(val) and val not in desc:
                parts.append(key+' — '+val+'.');break
        if parts:ps.append(' '.join(parts));desc='\n\n'.join(ps)
    # Keep short but precise entries short when the sources contain no more facts.
    return explanatory_context(card,desc)


def physical_paragraph(p):
    return bool(re.search(r'^(?:На (?:фотографии|изображении)|Внешне |Внешняя форма|Внешний |Корпус |Материал корпуса|Стальной корпус|Пластиковый корпус|Полиэтиленовый корпус|Изделие имеет|Общий (?:облик|силуэт))',p))


def history_paragraph(p):
    return bool(re.search(r'^(?:История |Во время |В годы |После |Разработка |Производство |Семейство (?:принято|появилось)|Первоначально |Раннее обозначение)',p))


def edit_card(card):
    if card['section']=='MEDICINE' or card['id'] in READY:return card.copy(),None
    original=card['body'];article,separator,oldnotes=original.partition('\n\n## Служебные сведения')
    notes=[];sections=[]
    for heading,text in split_sections(article):
        if heading in ('При обнаружении','Поведение при обнаружении','Что считать подозрительным','Сообщение и окружающие','До прибытия помощи'):
            sections.append((heading,text));continue
        text=edit_labels(clean(text,notes))
        if heading=='Страна и происхождение':text=text.rstrip(' ,;')
        if heading=='Класс' and card['categoryId']=='mortars':heading='Класс боеприпаса'
        sections.append((heading,text))
    pos=next((i for i,(h,t) in enumerate(sections) if h=='Описание'),None)
    assert pos is not None, card['id']
    desc=sections[pos][1]
    before_desc=desc
    if card['id'] in CURATED:desc='\n\n'.join(CURATED[card['id']])
    else:
        desc=named_intro(card,desc)
        # Remove exact duplicate sentences in the description, preserving model scopes.
        seen=set();new=[]
        for p in paragraphs(desc):
            ss=[]
            for sentence in sentences(p):
                if sentence in seen:continue
                seen.add(sentence);ss.append(sentence)
            if ss:new.append(' '.join(ss))
        desc='\n\n'.join(new)
        # A generic period sentence should follow the model introduction, rather
        # than restating the same classification as a second opening.
        if len(new)>1:
            lead=new[0]
            for i,p in enumerate(new[1:],1):
                if p.startswith(lead+' Период: '):new[i]='Исторический период: '+p[len(lead+' Период: '):]
            desc='\n\n'.join(new)
        desc=enrich_from_existing_facts(card,desc,article)
    ps=paragraphs(desc)
    assert ps,card['id']
    # Group prose by what the reader wants to know; do not pad articles with a
    # universal "history" or "appearance" section if no such facts are known.
    intro=[];appearance=[];history=[]
    for i,p in enumerate(ps):
        if i==0:intro.append(p)
        elif history_paragraph(p):history.append(p)
        elif physical_paragraph(p):appearance.append(p)
        else:intro.append(p)
    replacement=[('Описание','\n\n'.join(intro))]
    if appearance:replacement.append(('Внешний вид','\n\n'.join(appearance)))
    if history:replacement.append(('История и варианты','\n\n'.join(history)))
    # Every reviewed model gets a readable introduction; table and other model
    # sections are kept in the catalog even when that description was already good.
    sections[pos:pos+1]=replacement
    if card['id']=='pdf-source-method-v4':
        # Old release bookkeeping belongs to the archival provenance, rather
        # than an introductory article that ordinary readers open today.
        notes.append('Архив прежней памятки и истории каталога:\n\n'+article)
        sections=[('Описание',
            'Карточка помогает познакомиться с конкретной моделью: откуда она происходит, как выглядит и чем отличается от близких исполнений. Текст и таблица дополняют друг друга — описание объясняет особенности, а таблица позволяет быстро найти точную величину.'),
            ('Модель и семейство',
            'Одно название иногда объединяет несколько модификаций. Если указаны разные суффиксы или национальные исполнения, их характеристики читают раздельно. Размер корпуса, размер комплектного изделия и габариты транспортного контейнера относятся к разным предметам.'),
            ('Как понимать характеристики',
            'Полная масса изделия отличается от массы его содержимого. В графе размеров важно уточнение «без взрывателя», «со взрывателем» или название варианта. Приблизительный пересчёт единиц остаётся приблизительным; два расходящихся значения не превращаются в одно среднее.'),
            ('Если сведений мало',
            'Неустановленный год разработки не заменяют датой фотографии. Цвет опубликованного образца не считается обязательным цветом всех изделий. Если точная модификация не подтверждена, описание отмечает это прямо. УДМ-3, ПРМ-2М и КРАБ-М остаются неподтверждёнными обозначениями скрытого реестра.'),
            ('Фотографии и документы',
            'Подпись к изображению уточняет, показана ли сама модель, музейный экземпляр, учебный вариант или часть изделия. Ссылки на документы позволяют подробнее проверить сведения, но основной текст рассчитан на чтение без переходов по ссылкам.')]
        intro=[sections[0][1]]
    out='\n\n'.join(('## '+h+'\n\n' if h else '')+t for h,t in sections if h or t).rstrip()
    # Preserve any physical quantity that appeared only in an old prose clause.
    # Quantities are never recovered from source notes into the visible article.
    missing=[v for v in sorted(set(MEASURE.findall(article))) if v not in out]
    if missing:
        for p in paragraphs(before_desc):
            if any(v in p for v in missing):
                # Retain the complete factual paragraph and its scope, not a bare number.
                where=out.find('\n\n## При обнаружении')
                retained='\n\n'+p
                out=out[:where]+retained+out[where:] if where>=0 else out+retained
                missing=[v for v in missing if v not in out]
        if missing:raise AssertionError((card['id'],missing))
    if separator:out+=separator+oldnotes
    if notes:
        if not separator:out+='\n\n## Служебные сведения'
        out+='\n\nРедакторские примечания после текстовой редакции:\n\n'+'\n\n'.join(dict.fromkeys(notes))
    c=card.copy();c['body']=out
    # Use the actual model introduction as a preview, not a list of source checks.
    c['summary']=intro[0]
    if len(c['summary'])>600:
        first=sentences(c['summary']);short=[]
        for s in first:
            if len(' '.join(short+[s]))>600:break
            short.append(s)
        c['summary']=' '.join(short) or card['summary']
    assert len(c['summary'])<=600
    return c,{'id':c['id'],'title':c['title'],'category':c['categoryId'],
        'beforeWords':len(before_desc.split()),'afterWords':len(desc.split()),
        'curated':c['id'] in CURATED,'bodyChanged':out!=original,
        'summaryChanged':c['summary']!=card['summary'],'movedReferences':len(notes),
        'measurementsPreserved':len(set(MEASURE.findall(article)))}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path,required=True);parser.add_argument('--output',type=Path,default=ROOT/'content/catalog.json');args=parser.parse_args()
    data=json.loads(args.source.read_text());assert data['contentVersion']==150
    audit=[];baseline=[];cards=[]
    for card in data['cards']:
        c,row=edit_card(card);cards.append(c)
        article=card['body'].split('\n\n## Служебные сведения')[0]
        identity={k:v for k,v in card.items() if k not in ('body','summary')}
        baseline.append({'id':card['id'],'identity':hashlib.sha256(json.dumps(identity,ensure_ascii=False,sort_keys=True).encode()).hexdigest(),
          'measurements':sorted(set(MEASURE.findall(article))),
          'protectedBody':hashlib.sha256(card['body'].encode()).hexdigest() if card['section']=='MEDICINE' or card['id'] in READY else None,
          'protectedSummary':card['summary'] if card['section']=='MEDICINE' or card['id'] in READY else None,
          'tableValues':[v for table in table_blocks(article) for k,v in table],
          'notesLength':len(card['body'].partition('\n\n## Служебные сведения')[2]),
          'notes':hashlib.sha256(card['body'].partition('\n\n## Служебные сведения')[2].encode()).hexdigest()})
        if row:audit.append(row)
    assert len(audit)==1253
    data['cards']=cards;data['contentVersion']=151;data['catalogVersion']=151
    args.output.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    (ROOT/'tools/reader_150_baseline.json').write_text(json.dumps(baseline,ensure_ascii=False,indent=2)+'\n')
    report={'inputCatalog':150,'outputCatalog':151,'reviewed':len(audit),'medicalPreserved':20,'previouslyEditedPreserved':20,
        'bodyChanges':sum(x['bodyChanged'] for x in audit),'summaryChanges':sum(x['summaryChanged'] for x in audit),
        'individualEdits':sum(x['curated'] for x in audit),'cards':audit}
    (ROOT/'docs/READER_151_AUDIT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='cards'},ensure_ascii=False))

if __name__=='__main__':main()
