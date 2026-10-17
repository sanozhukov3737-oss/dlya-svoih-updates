package ru.dlyasvoih.app.data;

import java.nio.charset.StandardCharsets;
import java.util.*;

public final class HostSearchChecks {
    private static void encoded(String value) {
        System.out.println(Base64.getEncoder().encodeToString(value.getBytes(StandardCharsets.UTF_8)));
    }
    public static void main(String[] args) {
        if (args.length == 0) {
            if (!"елка".equals(CatalogSearch.normalize("ЁЛКА"))) throw new AssertionError("Unicode normalization");
            if (CatalogSearch.plan("+?!*") != null) throw new AssertionError("Operator input");
            if (!"\"46\"".equals(CatalogSearch.match("46"))) throw new AssertionError("Numeric prefix");
            for (String query : new String[]{"ТМ-46", "TM46", "ТM‑46", "РГД-5", "RGD5", "ПМН2", "PMN-2"}) {
                CatalogSearch.Plan plan = CatalogSearch.plan(query);
                if (plan == null || plan.whereArgs.isEmpty() || plan.rankArgs.isEmpty()) throw new AssertionError(query);
                long placeholders = (plan.whereSql + plan.rankSql).chars().filter(c -> c == '?').count();
                if (placeholders != plan.whereArgs.size() + plan.rankArgs.size()) throw new AssertionError("Bindings " + query);
            }
            System.out.println("Search checks passed");
            return;
        }
        CatalogSearch.Plan plan = CatalogSearch.plan(args[0]);
        if (plan == null) { System.out.println("NONE"); return; }
        encoded(plan.whereSql); System.out.println(plan.whereArgs.size());
        for (Object value : plan.whereArgs) encoded(value.toString());
        encoded(plan.rankSql); System.out.println(plan.rankArgs.size());
        for (Object value : plan.rankArgs) encoded(value.toString());
    }
}
