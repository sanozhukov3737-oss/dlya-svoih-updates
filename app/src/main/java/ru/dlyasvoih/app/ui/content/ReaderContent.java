package ru.dlyasvoih.app.ui.content;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

/** Separates articles from documentation; supports installed older catalogs too. */
public final class ReaderContent {
    private static final Set<String> NOTES = new HashSet<>(Arrays.asList(
        "Служебные сведения", "Статус проверки", "Источник описания", "Источник характеристик",
        "Примечания к источнику", "Примечания к источникам", "Ограничения сведений",
        "Что не подтверждено", "Редакционное решение", "Уточнение статуса"));
    private static final Set<String> MORTAR = new HashSet<>(Arrays.asList(
        "Основание", "Признаки распознавания", "Фото и визуальная сверка", "Границы карточки"));

    private ReaderContent() {}

    public static List<String> article(List<String> paragraphs, boolean mortar) {
        return partition(paragraphs, mortar, false);
    }

    public static List<String> notes(List<String> paragraphs) {
        return partition(paragraphs, false, true);
    }

    public static String searchableBody(String body) {
        // Keep exact separators: the import validator compares this text with
        // the bundled SQLite search field, including empty model separators.
        return String.join("\n\n", article(Arrays.asList(body.split("\\n\\n", -1)), false));
    }

    private static List<String> partition(List<String> paragraphs, boolean mortar, boolean collectNotes) {
        List<String> result = new ArrayList<>();
        boolean noteSection = false;
        boolean finalNotes = false;
        boolean presentationHidden = false;
        for (String paragraph : paragraphs) {
            ReferenceBodyParser.Block block = ReferenceBodyParser.parseBlock(paragraph);
            if (block.getKind() == ReferenceBodyParser.Kind.HEADING) {
                String heading = block.getText();
                finalNotes |= heading.equals("Служебные сведения");
                noteSection = finalNotes || NOTES.contains(heading);
                presentationHidden = mortar && MORTAR.contains(heading);
                if (heading.equals("Служебные сведения")) continue;
            }
            String text = paragraph.trim();
            boolean inlineNote = text.startsWith("Источник:") || text.startsWith("Источник дополнения:")
                || text.startsWith("Сведения о наполнении:") || text.startsWith("Уточнение справочных данных:");
            boolean note = noteSection || inlineNote;
            if (collectNotes ? note : !note && !presentationHidden) result.add(paragraph);
        }
        return Collections.unmodifiableList(result);
    }
}
