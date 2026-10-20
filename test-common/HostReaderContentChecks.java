package ru.dlyasvoih.app.ui.content;

import java.util.Arrays;
import java.util.List;

public final class HostReaderContentChecks {
    private static void check(boolean value, String message) {
        if (!value) throw new AssertionError(message);
    }
    public static void main(String[] args) throws Exception {
        if (args.length == 1) {
            for (String line : java.nio.file.Files.readAllLines(java.nio.file.Paths.get(args[0]))) {
                String body = new String(java.util.Base64.getDecoder().decode(line), java.nio.charset.StandardCharsets.UTF_8);
                System.out.println(java.util.Base64.getEncoder().encodeToString(
                    ReaderContent.searchableBody(body).getBytes(java.nio.charset.StandardCharsets.UTF_8)));
            }
            return;
        }
        List<String> current = Arrays.asList("## Описание", "Корпус — пластик.",
            "## Характеристики", "| Масса без взрывателя | 42 г |", "## При обнаружении", "Не трогайте.",
            "## Служебные сведения", "Исходная строка: | Масса | 99 г |", "## Вложенная запись", "Проверено.");
        check(ReaderContent.article(current, false).size() == 6, "Final notes leaked into article");
        check(ReaderContent.notes(current).size() == 3, "Documentation was lost");
        check(!ReaderContent.searchableBody(String.join("\n\n", current)).contains("99 г"), "Notes pollute search/comparison");
        check(ReaderContent.searchableBody(String.join("\n\n", current)).contains("без взрывателя"), "Measurement qualifier lost");
        List<String> old = Arrays.asList("## Описание", "Модель A.", "## Источник описания", "Документ 2003.",
            "## Характеристики B", "Модель B: 17 г.", "Сведения о наполнении: редакционная запись.", "## При обнаружении", "Не трогайте.");
        check(ReaderContent.article(old, false).contains("Модель B: 17 г."), "Variant heading was hidden");
        check(ReaderContent.notes(old).contains("Документ 2003."), "Older catalog notes lost");
        check(!ReaderContent.article(old, false).contains(old.get(6)), "Older inline note leaked");
        List<String> mortar = Arrays.asList("## Признаки распознавания", "Старая подсказка", "## Характеристики", "81 мм");
        check(ReaderContent.article(mortar, true).equals(Arrays.asList("## Характеристики", "81 мм")), "Mortar presentation changed");
        System.out.println("Reader content checks passed");
    }
}
