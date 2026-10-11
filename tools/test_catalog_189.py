"""Check release scope and render the actual Fagot article with production parsers."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / 'content/catalog.json').read_text())
BASE = json.loads((ROOT / 'docs/releases/catalog-189-baseline.json').read_text())
FAGOT_ID = 'atgm-9k111-fagot'


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':')).encode()).hexdigest()


class Catalog189Tests(unittest.TestCase):
    def test_only_fagot_body_changes_from_published_catalog_188(self):
        self.assertEqual((189, 189), (DATA['contentVersion'], DATA['catalogVersion']))
        self.assertEqual(BASE['countries'], digest(DATA['countries']))
        self.assertEqual(BASE['categories'], digest(DATA['categories']))
        self.assertEqual(set(BASE['cards']), {c['id'] for c in DATA['cards']})
        for card in DATA['cards']:
            if card['id'] == FAGOT_ID:
                self.assertEqual(BASE['fagotIdentity'], digest({k: v for k, v in card.items() if k != 'body'}))
                self.assertNotEqual(BASE['cards'][FAGOT_ID], digest(card))
            else:
                self.assertEqual(BASE['cards'][card['id']], digest(card), card['id'])

    def test_actual_reader_and_comparison_expose_variant_characteristics(self):
        java = shutil.which('java')
        self.assertIsNotNone(java, 'JDK is required for release verification')
        card = next(c for c in DATA['cards'] if c['id'] == FAGOT_ID)
        source = '''package ru.dlyasvoih.app.ui.content;
import java.nio.file.*;
import java.util.*;
public final class FagotReleaseChecks {
 public static void main(String[] args) throws Exception {
  String body = Files.readString(Path.of(args[0]));
  boolean found = false;
  for (String paragraph : ReaderContent.searchableBody(body).split("\\n\\n")) {
   ReferenceBodyParser.Block block = ReferenceBodyParser.parseBlock(paragraph);
   if (block.getKind() == ReferenceBodyParser.Kind.TABLE
       && block.getRows().stream().anyMatch(r -> r.getLabel().equals("Калибр"))) {
    if (block.getRows().size() != 7) throw new AssertionError("Incomplete characteristics table");
    found = true;
   }
  }
  if (!found) throw new AssertionError("Reader does not render characteristics");
  Map<String,String> facts = new LinkedHashMap<>();
  for (ComparisonContent.Row row : ComparisonContent.rows(body, "")) facts.put(row.label, row.left);
  if (!"9М111-2".equals(facts.get("Ракета"))) throw new AssertionError("Variant missing");
  if (!"120 мм".equals(facts.get("Калибр"))) throw new AssertionError("Caliber missing");
  if (!"70–2000 м".equals(facts.get("Дальность в каталоге VMZ"))) throw new AssertionError("Range missing");
  if (!facts.get("Масса ракеты по каталогу VMZ").contains("учёт контейнера не уточнён"))
   throw new AssertionError("Mass qualifier missing");
  System.out.println("Actual Fagot article renders 7 characteristics and exposes them in comparison");
 }
}'''
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            harness = folder / 'FagotReleaseChecks.java'
            harness.write_text(source)
            body_file = folder / 'fagot.txt'
            body_file.write_text(card['body'])
            sources = [ROOT / f'app/src/main/java/ru/dlyasvoih/app/ui/content/{name}.java'
                       for name in ('ReferenceBodyParser', 'ReaderContent', 'ComparisonContent')]
            compiled = subprocess.run([java, '-m', 'jdk.compiler/com.sun.tools.javac.Main', '-d', directory,
                                       *map(str, sources), str(harness)], capture_output=True, text=True, timeout=30)
            self.assertEqual(0, compiled.returncode, compiled.stderr)
            checked = subprocess.run([java, '-cp', directory,
                                      'ru.dlyasvoih.app.ui.content.FagotReleaseChecks', str(body_file)],
                                     capture_output=True, text=True, timeout=30)
            self.assertEqual(0, checked.returncode, checked.stderr)


if __name__ == '__main__':
    unittest.main()
