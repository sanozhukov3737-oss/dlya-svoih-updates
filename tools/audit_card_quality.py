"""Audit every catalog row and media reference without claiming a factual review.

Suspected duplicates, short articles and shared pictures are review candidates,
not automatic grounds for removing a card or declaring an image incorrect.
The actual Java reader parser determines whether each table will be formatted.
"""
import argparse
import base64
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import subprocess
import tempfile
import unicodedata

from PIL import Image
from build_catalog import ROOT, ASSETS, validate


def key(text):
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFKC', text)).strip().casefold()


def reader_tables(cards):
    """Use production parsing, rather than approximate Markdown heuristics."""
    code = r'''import java.nio.file.*; import java.nio.charset.*; import java.util.*;
import ru.dlyasvoih.app.ui.content.ReferenceBodyParser;
public class AuditReaderTables {
 public static void main(String[] args) throws Exception {
  for (String line: Files.readAllLines(Paths.get(args[0]))) {
   String[] f = line.split("\t", -1);
   String body = new String(Base64.getDecoder().decode(f[1]), StandardCharsets.UTF_8);
   int index = 0;
   for (String block: body.split("\\n\\n", -1)) {
    if (block.trim().startsWith("|") && block.contains("---")) {
     boolean valid = ReferenceBodyParser.parseBlock(block).getKind()
        == ReferenceBodyParser.Kind.TABLE;
     System.out.println(f[0] + "\t" + index + "\t" + valid);
    }
    index++;
   }
  }
 }
}'''
    with tempfile.TemporaryDirectory(prefix='catalog-reader-audit-') as directory:
        work = Path(directory)
        (work / 'AuditReaderTables.java').write_text(code)
        parser = ROOT / 'app/src/main/java/ru/dlyasvoih/app/ui/content/ReferenceBodyParser.java'
        subprocess.run(['java', '-m', 'jdk.compiler/com.sun.tools.javac.Main',
                        '-d', str(work), str(parser), str(work / 'AuditReaderTables.java')],
                       check=True, timeout=60, capture_output=True)
        (work / 'input.tsv').write_text('\n'.join(c['id'] + '\t' +
            base64.b64encode(c['body'].encode()).decode() for c in cards))
        result = subprocess.run(['java', '-cp', str(work), 'AuditReaderTables',
                                 str(work / 'input.tsv')], check=True,
                                capture_output=True, text=True, timeout=60)
    return [dict(cardId=f[0], block=int(f[1]), formatted=f[2] == 'true')
            for line in result.stdout.splitlines() if (f := line.split('\t'))]


def audit(source, database=None):
    source = Path(source)
    data = json.loads(source.read_text())
    cards = data['cards']
    errors, review = [], []
    # Existing import validation covers all IDs, relationships and image dimensions.
    try:
        validate(data)
    except (ValueError, KeyError, OSError) as error:
        errors.append(dict(kind='catalog-validation', detail=str(error)))
    media = {}
    title_groups, body_groups, picture_groups = defaultdict(list), defaultdict(list), defaultdict(list)
    short, missing_images, qualified_images = [], [], []
    sources_without_url = 0
    for card in cards:
        cid = card['id']
        title_groups[key(card['title'])].append(cid)
        body_groups[key(card['body'])].append(cid)
        for field, limit in [('title', 200), ('summary', 600), ('body', 100000)]:
            value = card[field]
            if not value.strip() or len(value) > limit:
                errors.append(dict(kind='invalid-text', cardId=cid, field=field))
            if '\ufffd' in value or re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', value):
                errors.append(dict(kind='text-encoding', cardId=cid, field=field))
        blocks = card['body'].split('\n\n')
        for index, block in enumerate(blocks):
            if block.startswith('## ') and (index == len(blocks)-1 or blocks[index+1].startswith('## ')):
                errors.append(dict(kind='empty-section', cardId=cid, heading=block))
            if index and len(block.strip()) > 40 and block.strip() == blocks[index-1].strip():
                review.append(dict(kind='adjacent-identical-blocks', cardId=cid, block=index))
        if len(card['body']) < 350:
            short.append(dict(cardId=cid, title=card['title'], characters=len(card['body'])))
        if not card['images']:
            missing_images.append(cid)
        if len(' · '.join(card['tags'])) > 2000:
            errors.append(dict(kind='tags-exceed-android-limit', cardId=cid))
        for picture in card['images']:
            if not picture['caption'].strip() or len(picture['caption']) > 600:
                errors.append(dict(kind='image-caption-android-limit', cardId=cid, imageId=picture['id']))
            if re.search(r'родствен|семейн|не подтвержд|не выда[её]тся|не установлен', picture['caption'], re.I):
                qualified_images.append(dict(cardId=cid, imageId=picture['id'], caption=picture['caption']))
            for field in ('localPath', 'thumbnailPath'):
                path = picture[field]
                if path in media:
                    continue
                try:
                    raw = (ASSETS / path).read_bytes()
                    with Image.open(ASSETS / path) as image:
                        image.load()
                        media[path] = dict(width=image.width, height=image.height,
                            bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
                except (OSError, ValueError) as error:
                    errors.append(dict(kind='media-decode', path=path, detail=str(error)))
            if picture['localPath'] in media:
                picture_groups[media[picture['localPath']]['sha256']].append(
                    dict(cardId=cid, imageId=picture['id'], path=picture['localPath']))
        for source_row in card['sources']:
            sources_without_url += source_row['url'] is None
            if not source_row['title'].strip() or len(source_row['title']) > 500:
                errors.append(dict(kind='source-title-android-limit', cardId=cid, sourceId=source_row['id']))
    tables = reader_tables(cards)
    errors += [dict(kind='unformatted-table', cardId=t['cardId'], block=t['block'])
               for t in tables if not t['formatted']]
    duplicate_titles = [ids for ids in title_groups.values() if len(ids) > 1]
    duplicate_bodies = [ids for ids in body_groups.values() if len(ids) > 1]
    shared_images = [rows for rows in picture_groups.values()
                     if len({r['cardId'] for r in rows}) > 1]
    db_result = None
    if database:
        with sqlite3.connect(f'file:{Path(database).resolve()}?mode=ro', uri=True) as db:
            integrity = db.execute('PRAGMA integrity_check').fetchone()[0]
            foreign_keys = db.execute('PRAGMA foreign_key_check').fetchall()
            actual = dict(db.execute('SELECT id,rowid FROM cards'))
            expected = {c['id']: c['rowid'] for c in cards}
            db_result = dict(integrity=integrity, foreignKeyViolations=len(foreign_keys),
                             cardIdsAndRowidsMatch=actual == expected,
                             contentVersion=db.execute("SELECT value FROM metadata WHERE key='content_version'").fetchone()[0])
            if integrity != 'ok' or foreign_keys or actual != expected:
                errors.append(dict(kind='database-integrity-or-identity'))
    return dict(contentVersion=data['contentVersion'],
        catalogSha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        coverage=dict(cards=len(cards), sections=dict(Counter(c['section'] for c in cards)),
            imageReferences=sum(len(c['images']) for c in cards), uniqueMediaFilesDecoded=len(media),
            sources=sum(len(c['sources']) for c in cards), tables=len(tables)),
        confirmedStructuralErrors=errors, reviewCandidates=review,
        duplicateTitleGroups=duplicate_titles, duplicateBodyGroups=duplicate_bodies,
        sharedImageGroups=shared_images, shortArticles=short,
        cardsWithoutImages=missing_images, explicitlyQualifiedImages=qualified_images,
        localDocumentSourceReferences=sources_without_url, database=db_result,
        media=media,
        scope='All catalog rows and referenced media checked mechanically. Duplicate identities and photo identity require recorded editorial decisions; this is not independent verification of every technical or medical statement.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT / 'content/catalog.json')
    parser.add_argument('--database', type=Path)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.source, args.database)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(dict(coverage=result['coverage'],
        structuralErrors=len(result['confirmedStructuralErrors']),
        duplicateTitleGroups=len(result['duplicateTitleGroups']),
        sharedImageGroups=len(result['sharedImageGroups']), shortArticles=len(result['shortArticles'])),
        ensure_ascii=False))
