package ru.dlyasvoih.app.ui.content;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Objects;
import java.util.regex.Pattern;

/**
 * Small, non-executing formatter for a single existing body paragraph.
 * It deliberately is not a full Markdown or HTML renderer. Unsupported or
 * malformed syntax stays visible as the original text, without dropping data.
 */
public final class ReferenceBodyParser {
    private static final Pattern SEPARATOR = Pattern.compile(":?-{3,}:?");

    private ReferenceBodyParser() {}

    public enum Kind { TEXT, HEADING, TABLE }

    public static final class Row {
        private final String label;
        private final String value;

        private Row(String label, String value) {
            this.label = label;
            this.value = value;
        }

        public String getLabel() { return label; }
        public String getValue() { return value; }
    }

    public static final class Block {
        private final Kind kind;
        private final String text;
        private final Row header;
        private final List<Row> rows;

        private Block(Kind kind, String text, Row header, List<Row> rows) {
            this.kind = kind;
            this.text = text;
            this.header = header;
            this.rows = Collections.unmodifiableList(new ArrayList<>(rows));
        }

        public Kind getKind() { return kind; }
        public String getText() { return text; }
        public Row getHeader() { return header; }
        public List<Row> getRows() { return rows; }
    }

    /** One input block always produces one output block, preserving reading indices. */
    public static Block parseBlock(String original) {
        Objects.requireNonNull(original, "original");
        String normalized = original.replace("\r\n", "\n").replace('\r', '\n').trim();
        if (normalized.startsWith("## ") && normalized.indexOf('\n') < 0) {
            String heading = normalized.substring(3).trim();
            if (!heading.isEmpty()) return new Block(Kind.HEADING, heading, null, Collections.emptyList());
        }

        String[] lines = normalized.split("\n", -1);
        if (lines.length >= 3) {
            List<String> header = parseRow(lines[0]);
            List<String> divider = parseRow(lines[1]);
            if (header.size() == 2 && !header.get(0).isEmpty() && !header.get(1).isEmpty()
                    && divider.size() == 2 && SEPARATOR.matcher(divider.get(0)).matches()
                    && SEPARATOR.matcher(divider.get(1)).matches()) {
                List<Row> rows = new ArrayList<>();
                for (int i = 2; i < lines.length; i++) {
                    List<String> cells = parseRow(lines[i]);
                    if (cells.size() != 2) return plain(original);
                    rows.add(new Row(cells.get(0), cells.get(1)));
                }
                return new Block(Kind.TABLE, original, new Row(header.get(0), header.get(1)), rows);
            }
        }
        return plain(original);
    }

    private static Block plain(String original) {
        return new Block(Kind.TEXT, original, null, Collections.emptyList());
    }

    private static List<String> parseRow(String source) {
        String line = source.trim();
        List<String> cells = new ArrayList<>();
        StringBuilder cell = new StringBuilder();
        for (int i = 0; i < line.length(); i++) {
            char character = line.charAt(i);
            if (character == '\\' && i + 1 < line.length()
                    && (line.charAt(i + 1) == '|' || line.charAt(i + 1) == '\\')) {
                cell.append(line.charAt(++i));
            } else if (character == '|') {
                cells.add(cell.toString().trim());
                cell.setLength(0);
            } else {
                cell.append(character);
            }
        }
        cells.add(cell.toString().trim());
        if (line.startsWith("|") && !cells.isEmpty()) cells.remove(0);
        if (line.endsWith("|") && !cells.isEmpty() && cells.get(cells.size() - 1).isEmpty()) {
            cells.remove(cells.size() - 1);
        }
        return cells;
    }
}
