package ru.dlyasvoih.app.ui.content;

import java.util.List;

public final class HostComparisonChecks {
    static void check(boolean value) { if (!value) throw new AssertionError(); }
    static String table(String rows) { return "| Параметр | Значение |\n| --- | --- |\n" + rows; }
    public static void main(String[] args) {
        String left = "## Характеристики\n\n" + table("| Цвет | Красный |\n| Высота | 10 см |\n| Материал | Пластик |");
        String right = "## Характеристики\n\n" + table("| Высота | 20 см |\n| цвет | Синий |\n| Ширина | 5 см |");
        List<ComparisonContent.Row> rows = ComparisonContent.rows(left, right);
        check(rows.size() == 4);
        check(rows.get(0).left.equals("Красный") && rows.get(0).right.equals("Синий"));
        check(rows.get(1).left.equals("10 см") && rows.get(1).right.equals("20 см"));
        check(rows.get(2).right == null && rows.get(3).left == null);
        check(ComparisonContent.rows(left, "Описание без таблицы").size() == 3);
        check(ComparisonContent.rows("Описание", "Описание").isEmpty());
        String escaped = table("| Материал | Сталь \\| пластик |\n| Масса, г | 20 |\n| Масса без крышки, г | 18 |");
        rows = ComparisonContent.rows(escaped, table("| Масса, кг | 1 |"));
        check(rows.size() == 4 && rows.get(0).left.equals("Сталь | пластик"));
        check(rows.get(1).right == null && rows.get(2).right == null);
        String notes = left + "\n\n## Служебные сведения\n\n" + table("| Внутренняя пометка | Скрыть |");
        check(ComparisonContent.rows(notes, right).size() == 4);
        String variants = "## Вариант А\n\n" + table("| Цвет | Красный |")
                + "\n\n## Вариант Б\n\n" + table("| Цвет | Синий |");
        rows = ComparisonContent.rows(variants, "");
        check(rows.size() == 1 && rows.get(0).left.equals("Вариант А: Красный\nВариант Б: Синий"));
        String many = "";
        for (int i = 0; i < 20; i++) many += "| Поле " + i + " | Значение " + i + " |\n";
        check(ComparisonContent.rows(table(many.trim()), "").size() == 20);
        System.out.println("Comparison checks passed");
    }
}
