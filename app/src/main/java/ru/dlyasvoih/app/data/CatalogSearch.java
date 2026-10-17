package ru.dlyasvoih.app.data;

import java.text.Normalizer;
import java.util.*;
import java.util.regex.*;

/** Search names independently of the FTS index; retain full-text results after name hits. */
public final class CatalogSearch {
    private static final int MAX_LENGTH = 160;
    private static final Pattern WORD = Pattern.compile("[\\p{L}\\p{N}]+");
    private static final Pattern PART = Pattern.compile("[\\p{L}]+|[\\p{N}]+");
    private static final String PADDED_TITLE = "(' ' || c.sortTitle || ' ')";
    private static final String CYRILLIC = "абвгдежзийклмнопрстуфхцчшщъыьэюя";
    private static final String[] LATIN = {"a","b","v","g","d","e","zh","z","i","y","k","l","m","n","o","p","r","s","t","u","f","kh","ts","ch","sh","shch","","y","","e","yu","ya"};
    private CatalogSearch() {}

    public static String normalize(String value) {
        return Normalizer.normalize(value, Normalizer.Form.NFKC).toLowerCase(Locale.ROOT).replace('ё', 'е');
    }
    private static List<String> words(String value, Pattern pattern, int limit) {
        Set<String> unique = new LinkedHashSet<>();
        Matcher matcher = pattern.matcher(value);
        while (matcher.find() && unique.size() < limit) unique.add(matcher.group());
        return new ArrayList<>(unique);
    }
    private static boolean numeric(String value) {
        for (int i = 0; i < value.length(); i++) if (!Character.isDigit(value.charAt(i))) return false;
        return !value.isEmpty();
    }
    private static String latin(String value) {
        StringBuilder result = new StringBuilder();
        for (int i = 0; i < value.length(); i++) {
            char ch = value.charAt(i);
            int index = CYRILLIC.indexOf(ch);
            result.append(index < 0 ? String.valueOf(ch) : LATIN[index]);
        }
        return result.toString();
    }
    private static String cyrillic(String value) {
        StringBuilder result = new StringBuilder();
        // Longest transliteration first; ordinary Latin designations remain an alternative.
        String[] source = {"shch","zh","kh","ts","ch","sh","yu","ya","a","b","v","g","d","e","z","i","y","k","l","m","n","o","p","r","s","t","u","f","h"};
        String[] target = {"щ","ж","х","ц","ч","ш","ю","я","а","б","в","г","д","е","з","и","й","к","л","м","н","о","п","р","с","т","у","ф","х"};
        for (int i = 0; i < value.length();) {
            boolean replaced = false;
            for (int j = 0; j < source.length; j++) if (value.startsWith(source[j], i)) {
                result.append(target[j]); i += source[j].length(); replaced = true; break;
            }
            if (!replaced) result.append(value.charAt(i++));
        }
        return result.toString();
    }
    private static List<String> variants(String value, boolean model) {
        SortedSet<String> result = new TreeSet<>();
        result.add(value);
        if (model) { String roman = latin(value); result.add(roman); result.add(cyrillic(roman)); }
        result.remove("");
        return new ArrayList<>(result);
    }
    private static String ftsTerm(String value, boolean model) {
        List<String> terms = new ArrayList<>();
        for (String variant : variants(value, model)) terms.add("\"" + variant + (numeric(variant) ? "" : "*") + "\"");
        return terms.size() == 1 ? terms.get(0) : "(" + String.join(" OR ", terms) + ")";
    }
    public static String match(String value) {
        String normalized = normalize(value.substring(0, Math.min(value.length(), MAX_LENGTH)));
        List<String> raw = words(normalized, WORD, 8);
        if (raw.isEmpty()) return null;
        boolean model = normalized.codePoints().anyMatch(Character::isDigit);
        List<String> terms = new ArrayList<>();
        for (String word : raw) {
            List<String> parts = words(word, PART, 16);
            String joined = ftsTerm(word, model);
            if (parts.size() > 1) {
                List<String> split = new ArrayList<>();
                for (String part : parts) split.add(ftsTerm(part, model));
                joined = "(" + joined + " OR (" + String.join(" AND ", split) + "))";
            }
            terms.add(joined);
        }
        return String.join(" AND ", terms);
    }
    public static final class Plan {
        public final String whereSql, rankSql;
        public final List<Object> whereArgs, rankArgs;
        Plan(String whereSql, List<Object> whereArgs, String rankSql, List<Object> rankArgs) {
            this.whereSql = whereSql; this.whereArgs = Collections.unmodifiableList(whereArgs);
            this.rankSql = rankSql; this.rankArgs = Collections.unmodifiableList(rankArgs);
        }
    }
    private static String titlePredicate(List<String> parts, boolean model, boolean strictNumbers, List<Object> args) {
        List<String> all = new ArrayList<>();
        for (String part : parts) {
            List<String> alternatives = new ArrayList<>();
            for (String variant : variants(part, model)) {
                alternatives.add(PADDED_TITLE + " GLOB ?");
                args.add(numeric(variant)
                    ? "*[^0-9]" + variant + (strictNumbers ? "[^0-9a-zа-яё]*" : "[^0-9]*")
                    : "*[^a-zа-яё]" + variant + "*");
            }
            all.add("(" + String.join(" OR ", alternatives) + ")");
        }
        return "(" + String.join(" AND ", all) + ")";
    }
    public static Plan plan(String value) {
        String normalized = normalize(value.substring(0, Math.min(value.length(), MAX_LENGTH)));
        String fullText = match(normalized);
        if (fullText == null) return null;
        List<String> parts = words(normalized, PART, 16);
        boolean model = normalized.codePoints().anyMatch(Character::isDigit);
        List<Object> whereArgs = new ArrayList<>();
        String title = titlePredicate(parts, model, false, whereArgs);
        whereArgs.add(fullText);
        String where = "(" + title + " OR c.rowid IN (SELECT rowid FROM cards_fts WHERE cards_fts MATCH ?))";
        String compactTitle = "c.sortTitle";
        for (String separator : new String[]{" ","-","‐","‑","–","—",".",",","_"})
            compactTitle = "replace(" + compactTitle + ",'" + separator + "','')";
        String compactQuery = String.join("", words(normalized, PART, 16));
        List<String> exact = variants(compactQuery, model);
        List<Object> rankArgs = new ArrayList<>(exact);
        String exactMatch = compactTitle + " IN (" + String.join(",", Collections.nCopies(exact.size(), "?")) + ")";
        String strictTitle = titlePredicate(parts, model, true, rankArgs);
        String broadTitle = titlePredicate(parts, model, false, rankArgs);
        // Titles have at most 200 characters. Short, exact model names precede longer variants.
        String rank = "CASE WHEN " + exactMatch + " THEN 0 WHEN " + strictTitle
            + " THEN 1000 + length(c.sortTitle) WHEN " + broadTitle
            + " THEN 2000 + length(c.sortTitle) ELSE 3000 END";
        return new Plan(where, whereArgs, rank, rankArgs);
    }
}
