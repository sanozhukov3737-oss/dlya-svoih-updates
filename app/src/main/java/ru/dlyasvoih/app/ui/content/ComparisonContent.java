package ru.dlyasvoih.app.ui.content;

import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** Align source labels, never row positions or measurements with different qualifiers. */
public final class ComparisonContent {
    private ComparisonContent() {}

    private static final Pattern UNIT = Pattern.compile("^(.+?)(?:,\\s*|\\s*\\()(мм|см|м|г|кг)\\)?$", Pattern.CASE_INSENSITIVE);
    private static final Pattern MASS_VALUE = Pattern.compile("(?iu)(?<![\\p{L}])(?:кг|г|kg|g)(?![\\p{L}])");
    private static final Pattern LENGTH_VALUE = Pattern.compile("(?iu)(?<![\\p{L}])(?:мм|см|м|mm|cm|m)(?![\\p{L}])");
    private static final Set<String> GENERAL_HEADINGS = new LinkedHashSet<>(java.util.Arrays.asList(
        "характеристики", "основные характеристики", "технические характеристики", "ттх", "параметры", "сведения"));

    public static final class TableRow {
        public final String label;
        public final List<String> values;
        private TableRow(String label, List<String> values) {
            this.label = label;
            this.values = Collections.unmodifiableList(values);
        }
    }

    public static final class Row {
        public final String label;
        public final String left;
        public final String right;
        private Row(String label, String left, String right) {
            this.label = label;
            this.left = left;
            this.right = right;
        }
    }

    private static final class Fact {
        final String label;
        final Map<String, Set<String>> sections = new LinkedHashMap<>();
        Fact(String label) { this.label = label; }
        String value() {
            List<String> values = new ArrayList<>();
            for (Map.Entry<String, Set<String>> entry : sections.entrySet()) {
                String text = String.join("; ", entry.getValue());
                String section = entry.getKey();
                boolean qualify = !section.isEmpty() && !GENERAL_HEADINGS.contains(normalize(section));
                values.add(qualify ? section + ": " + text : text);
            }
            return String.join("\n", values);
        }
    }

    public static List<Row> rows(String leftBody, String rightBody) {
        List<Row> rows = new ArrayList<>();
        for (TableRow row : table(java.util.Arrays.asList(leftBody, rightBody))) {
            rows.add(new Row(row.label, row.values.get(0), row.values.get(1)));
        }
        return Collections.unmodifiableList(rows);
    }

    public static List<TableRow> table(List<String> bodies) {
        if (bodies.size() < 2 || bodies.size() > 3) throw new IllegalArgumentException("Compare two or three articles");
        List<Map<String, Fact>> columns = new ArrayList<>();
        Set<String> keys = new LinkedHashSet<>();
        for (String body : bodies) {
            Map<String, Fact> column = facts(body);
            columns.add(column);
            keys.addAll(column.keySet());
        }
        List<TableRow> rows = new ArrayList<>();
        for (String key : keys) {
            String label = null;
            List<String> values = new ArrayList<>();
            for (Map<String, Fact> column : columns) {
                Fact fact = column.get(key);
                if (fact != null && label == null) label = fact.label;
                values.add(fact == null ? null : fact.value());
            }
            rows.add(new TableRow(label, values));
        }
        return Collections.unmodifiableList(rows);
    }

    private static String normalize(String label) {
        return label.toLowerCase(Locale.ROOT).replace('ё', 'е').replace('\u00a0', ' ')
            .replaceAll("\\s+", " ").replaceAll(":$", "").trim();
    }

    private static Map<String, Fact> facts(String body) {
        Map<String, Fact> facts = new LinkedHashMap<>();
        String section = "";
        for (String paragraph : ReaderContent.searchableBody(body).split("\\n\\n")) {
            ReferenceBodyParser.Block block = ReferenceBodyParser.parseBlock(paragraph);
            if (block.getKind() == ReferenceBodyParser.Kind.HEADING) section = block.getText();
            if (block.getKind() != ReferenceBodyParser.Kind.TABLE) continue;
            for (ReferenceBodyParser.Row row : block.getRows()) {
                String label = row.getLabel().trim(), value = row.getValue().trim();
                if (label.isEmpty() || value.isEmpty()) continue;
                String key = normalize(label);
                Matcher unit = UNIT.matcher(key);
                if (unit.matches()) {
                    String name = unit.group(1).trim(), symbol = unit.group(2);
                    boolean mass = symbol.equals("г") || symbol.equals("кг");
                    key = name + (mass ? " [mass]" : " [length]");
                    label = label.replaceFirst("(?:,\\s*|\\s*\\()(?:мм|см|м|г|кг)\\)?$", "").trim();
                    Pattern existing = mass ? MASS_VALUE : LENGTH_VALUE;
                    if (value.matches("(?s).*\\d.*") && !existing.matcher(value).find()) value += " " + symbol;
                } else if (key.startsWith("масса") && MASS_VALUE.matcher(value).find()) {
                    key += " [mass]";
                } else if (key.matches("(?:длина|диаметр|высота|ширина|калибр|габариты|размеры)(?: .*)?")
                        && LENGTH_VALUE.matcher(value).find()) {
                    key += " [length]";
                }
                Fact fact = facts.get(key);
                if (fact == null) {
                    fact = new Fact(label);
                    facts.put(key, fact);
                }
                Set<String> values = fact.sections.get(section);
                if (values == null) {
                    values = new LinkedHashSet<>();
                    fact.sections.put(section, values);
                }
                values.add(value);
            }
        }
        return facts;
    }
}
