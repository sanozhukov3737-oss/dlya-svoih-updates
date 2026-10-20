package ru.dlyasvoih.app.ui;

import java.text.Normalizer;
import java.util.*;
import java.util.regex.Pattern;

/** Search the small ordered title index, without loading article bodies or pictures. */
public final class ReaderIndex {
    private static final Pattern SEPARATORS = Pattern.compile("[^\\p{L}\\p{N}]");
    private final List<String> titles;

    public ReaderIndex(List<String> titles) {
        this.titles = new ArrayList<>(titles.size());
        for (String title : titles) this.titles.add(normalize(title));
    }

    private static String normalize(String value) {
        return SEPARATORS.matcher(Normalizer.normalize(value, Normalizer.Form.NFKC)
                .toLowerCase(Locale.ROOT).replace('ё', 'е')).replaceAll("");
    }

    public List<Integer> find(String input) {
        String raw = input.trim();
        List<Integer> result = new ArrayList<>();
        if (raw.matches("[0-9]+")) {
            try {
                int index = Integer.parseInt(raw) - 1;
                if (index >= 0 && index < titles.size()) result.add(index);
            } catch (NumberFormatException ignored) { }
            return result;
        }
        String query = normalize(raw);
        if (!raw.isEmpty() && query.isEmpty()) return result;
        for (int i = 0; i < titles.size(); i++) {
            if (titles.get(i).contains(query)) result.add(i);
        }
        return result;
    }
}
