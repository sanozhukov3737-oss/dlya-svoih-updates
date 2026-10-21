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
        check(rows.size() == 3 && rows.get(0).left.equals("Сталь | пластик"));
        check(rows.get(1).label.equals("Масса"));
        check(rows.get(1).left.equals("20 г") && rows.get(1).right.equals("1 кг"));
        check(rows.get(2).left.equals("18 г") && rows.get(2).right == null);
        String notes = left + "\n\n## Служебные сведения\n\n" + table("| Внутренняя пометка | Скрыть |");
        check(ComparisonContent.rows(notes, right).size() == 4);
        String variants = "## Вариант А\n\n" + table("| Цвет | Красный |")
                + "\n\n## Вариант Б\n\n" + table("| Цвет | Синий |");
        rows = ComparisonContent.rows(variants, "");
        check(rows.size() == 1 && rows.get(0).left.equals("Вариант А: Красный\nВариант Б: Синий"));
        List<ComparisonContent.TableRow> three = ComparisonContent.table(java.util.Arrays.asList(
            table("| Масса, г | 20 |\n| Масса без крышки, г | 18 |"),
            table("| Масса, кг | 1 |"), table("| Масса | 2 кг |\n| Цвет | Синий |")));
        check(three.size() == 3 && three.get(0).values.size() == 3);
        check(three.get(0).values.equals(java.util.Arrays.asList("20 г", "1 кг", "2 кг")));
        check(three.get(1).values.equals(java.util.Arrays.asList("18 г", null, null)));
        check(three.get(2).values.equals(java.util.Arrays.asList(null, null, "Синий")));
        rows = ComparisonContent.rows("## Вариант А\n\n" + table("| Масса (кг) | 3 |"),
            "## Вариант Б\n\n" + table("| Масса, кг | 4 кг |"));
        check(rows.size() == 1 && rows.get(0).left.equals("Вариант А: 3 кг") && rows.get(0).right.equals("Вариант Б: 4 кг"));
        rows = ComparisonContent.rows(table("| Высота, мм | 40 |\n| Высота без крышки, мм | 30 |"),
            table("| Высота, см | 4 |\n| Высота без крышки | Не указана |"));
        check(rows.size() == 3 && rows.get(0).left.equals("40 мм") && rows.get(0).right.equals("4 см"));
        check(rows.get(1).right == null && rows.get(2).left == null);
        String many = "";
        for (int i = 0; i < 20; i++) many += "| Поле " + i + " | Значение " + i + " |\n";
        check(ComparisonContent.rows(table(many.trim()), "").size() == 20);
        System.out.println("Comparison checks passed");
    }
}
