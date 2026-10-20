"""Derive search fields with the same Java code used by the Android importer.

The legacy projection remains explicit for imported published cards. New cards
use the reader projection; no stored searchText override can become stale.
Requires the JDK already needed to build the Android application.
"""
import base64
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
JAVA = r'''import java.nio.file.*; import java.nio.charset.*; import java.util.*;
import ru.dlyasvoih.app.data.CatalogSearch;
import ru.dlyasvoih.app.ui.content.ReaderContent;
public class CatalogProjection {
  public static void main(String[] args) throws Exception {
    for (String line : Files.readAllLines(Paths.get(args[0]))) {
      String[] f = line.split("\t", -1);
      for (int i=0; i<f.length; i++) f[i] = new String(
          Base64.getDecoder().decode(f[i]), StandardCharsets.UTF_8);
      String legacy = CatalogSearch.normalize(String.join(" ", f[0], f[1], f[2], f[3]));
      String reader = CatalogSearch.normalize(String.join(" ", f[0], f[1],
          ReaderContent.searchableBody(f[2]), f[3]));
      System.out.println(Base64.getEncoder().encodeToString(legacy.getBytes(StandardCharsets.UTF_8))
          + "\t" + Base64.getEncoder().encodeToString(reader.getBytes(StandardCharsets.UTF_8)));
    }
  }
}'''


def projections(cards):
    with tempfile.TemporaryDirectory(prefix='catalog-projection-') as directory:
        work = Path(directory)
        helper = work / 'CatalogProjection.java'
        helper.write_text(JAVA, encoding='utf-8')
        production = ROOT / 'app/src/main/java/ru/dlyasvoih/app'
        subprocess.run(['java', '-m', 'jdk.compiler/com.sun.tools.javac.Main', '-d', str(work),
            str(production / 'data/CatalogSearch.java'),
            str(production / 'ui/content/ReferenceBodyParser.java'),
            str(production / 'ui/content/ReaderContent.java'), str(helper)], check=True, timeout=60)
        payload = work / 'cards.tsv'
        payload.write_text('\n'.join('\t'.join(base64.b64encode(value.encode()).decode()
            for value in (card['title'], card['summary'], card['body'], ' '.join(card['tags'])))
            for card in cards) + '\n', encoding='ascii')
        result = subprocess.run(['java', '-cp', str(work), 'CatalogProjection', str(payload)],
            capture_output=True, text=True, check=True, timeout=60)
        pairs = [[base64.b64decode(value).decode() for value in line.split('\t')]
            for line in result.stdout.splitlines()]
        if len(pairs) != len(cards):
            raise ValueError('Incomplete Java search projection')
        return {card['id']: dict(zip(('legacy', 'reader'), pair, strict=True))
            for card, pair in zip(cards, pairs, strict=True)}


def search_fields(cards):
    pairs = projections(cards)
    return {card['id']: pairs[card['id']][card.get('searchProjection', 'reader')] for card in cards}
