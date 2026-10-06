package ru.dlyasvoih.app.ui.content;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** Indexes the rendered article only; never searches hidden documentation. */
public final class ReaderNavigation {
    private ReaderNavigation() {}

    public static final class Section {
        public final String title;
        public final int paragraphIndex;
        private Section(String title, int index) { this.title = title; paragraphIndex = index; }
    }

    public static List<Section> sections(List<String> paragraphs) {
        List<Section> result = new ArrayList<>();
        for (int i = 0; i < paragraphs.size(); i++) {
            ReferenceBodyParser.Block block = ReferenceBodyParser.parseBlock(paragraphs.get(i));
            if (block.getKind() == ReferenceBodyParser.Kind.HEADING) result.add(new Section(block.getText(), i));
        }
        return Collections.unmodifiableList(result);
    }

    /** Literal, Unicode-aware search; regex metacharacters are ordinary text. */
    public static List<int[]> ranges(String text, String query) {
        String term = query.trim();
        if (term.isEmpty()) return Collections.emptyList();
        Matcher matcher = Pattern.compile(Pattern.quote(term), Pattern.CASE_INSENSITIVE | Pattern.UNICODE_CASE).matcher(text);
        List<int[]> result = new ArrayList<>();
        while (matcher.find()) result.add(new int[] { matcher.start(), matcher.end() });
        return result;
    }

    /** Each result is a visible paragraph, heading or table containing the query. */
    public static List<Integer> matchingParagraphs(List<String> paragraphs, String query) {
        if (query.trim().isEmpty()) return Collections.emptyList();
        List<Integer> result = new ArrayList<>();
        for (int i = 0; i < paragraphs.size(); i++) {
            ReferenceBodyParser.Block block = ReferenceBodyParser.parseBlock(paragraphs.get(i));
            boolean found;
            if (block.getKind() == ReferenceBodyParser.Kind.TABLE) {
                found = !ranges(block.getHeader().getLabel(), query).isEmpty()
                    || !ranges(block.getHeader().getValue(), query).isEmpty();
                for (ReferenceBodyParser.Row row : block.getRows()) {
                    found |= !ranges(row.getLabel(), query).isEmpty() || !ranges(row.getValue(), query).isEmpty();
                }
            } else found = !ranges(block.getText(), query).isEmpty();
            if (found) result.add(i);
        }
        return Collections.unmodifiableList(result);
    }
}
