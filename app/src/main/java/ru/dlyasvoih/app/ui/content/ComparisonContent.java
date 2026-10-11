package ru.dlyasvoih.app.ui.content;

import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

/** Align source labels, never row positions or measurements with different qualifiers. */
public final class ComparisonContent {
    private ComparisonContent() {}

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
            boolean qualify = sections.size() > 1;
            for (Map.Entry<String, Set<String>> entry : sections.entrySet()) {
                String text = String.join("; ", entry.getValue());
                values.add(qualify && !entry.getKey().isEmpty() ? entry.getKey() + ": " + text : text);
            }
            return String.join("\n", values);
        }
    }

    public static List<Row> rows(String leftBody, String rightBody) {
        Map<String, Fact> left = facts(leftBody);
        Map<String, Fact> right = facts(rightBody);
        Set<String> keys = new LinkedHashSet<>(left.keySet());
        keys.addAll(right.keySet());
        List<Row> rows = new ArrayList<>();
        for (String key : keys) {
            Fact a = left.get(key), b = right.get(key);
            rows.add(new Row(a != null ? a.label : b.label,
                    a == null ? null : a.value(), b == null ? null : b.value()));
        }
        return Collections.unmodifiableList(rows);
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
                String key = label.toLowerCase(Locale.ROOT).replace('ё', 'е')
                        .replace('\u00a0', ' ').replaceAll("\\s+", " ").replaceAll(":$", "").trim();
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
