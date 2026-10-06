package ru.dlyasvoih.app.data;

import java.util.Arrays;
import java.util.Collections;
import java.util.List;

/** Explicit model series. Similar names alone do not establish a family. */
public final class CardFamilies {
    private static final List<List<String>> GROUPS = Arrays.asList(
        Arrays.asList("eng-pmn", "eng-pmn-2", "ref-v8-pmn-3", "ref-v8-pmn-4"),
        Arrays.asList("eng-mon-50", "ref-v8-mon-90", "ref-v8-mon-100", "ref-v8-mon-200"),
        Arrays.asList("eng-tm-62m", "ref-v8-tm-62p", "ref-v8-tm-62p3", "mine-audit-v25-su-tm-62b",
            "mine-audit-v25-su-tm-62d", "mine-audit-v25-su-tm-62p2", "mine-audit-v25-su-tm-62t"),
        Arrays.asList("ref-v8-pmd-6", "ref-v8-pmd-6m"),
        Arrays.asList("grenade-rgn", "grenade-rgo")
    );

    private CardFamilies() {}
    public static List<String> relatedIds(String id) {
        for (List<String> group : GROUPS) if (group.contains(id)) return Collections.unmodifiableList(group);
        return Collections.emptyList();
    }
    public static boolean sameFamily(String first, String second) {
        return !first.equals(second) && relatedIds(first).contains(second);
    }
}
