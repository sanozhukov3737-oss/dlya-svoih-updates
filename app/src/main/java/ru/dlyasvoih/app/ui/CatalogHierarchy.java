package ru.dlyasvoih.app.ui;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collection;
import java.util.Collections;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;

/** Presentation-only grouping. UI groups never become database category filters. */
public final class CatalogHierarchy {
    public static final String ENGINEERING_GROUP = "@engineering";
    public static final String INITIATION_GROUP = "@initiation";
    private static final Set<String> HIDDEN_CATEGORIES = Collections.unmodifiableSet(
            new LinkedHashSet<>(Arrays.asList("audit-candidates", "reference")));
    private static final List<String> ENGINEERING = Collections.unmodifiableList(Arrays.asList(
            "mines-antipersonnel", "mines-antitank", "mines-antibottom", "mines-antivehicle",
            "mines-naval", "mines-anchored", "mines-antiland", "charges", "mines-special", "ied", "engineering"));
    private static final List<String> INITIATION = Collections.unmodifiableList(Arrays.asList(
            "ignition-electric", "detonators-caps", "primers", "detonators-electric",
            "fuse-cord", "detonating-cord", "sapper-wires", "blasting-machines", "measuring-instruments",
            "ignition-tubes", "mine-fuzes", "grenade-fuzes",
            "artillery-fuzes", "detonators-nonelectric", "detonators-electronic", "fuzes"));
    private static final List<String> ROOT_CATEGORIES = Collections.unmodifiableList(Arrays.asList(
            "grenades", "mortars", "artillery", "cannon-ammunition", "rockets-recoilless",
            "air-munitions", "submunitions"));

    private CatalogHierarchy() { }

    public static boolean isVisibleCategory(String id) {
        return !HIDDEN_CATEGORIES.contains(id);
    }

    public static List<String> engineeringIds(Collection<String> availableIds) {
        return present(ENGINEERING, availableIds);
    }

    public static List<String> initiationIds(Collection<String> availableIds) {
        return present(INITIATION, availableIds);
    }

    private static List<String> present(List<String> ordered, Collection<String> availableIds) {
        Set<String> available = new LinkedHashSet<>(availableIds);
        List<String> result = new ArrayList<>();
        for (String id : ordered) if (available.contains(id)) result.add(id);
        return Collections.unmodifiableList(result);
    }

    /** Visible categories stay reachable, including IDs supplied by future content updates. */
    public static List<String> rootIds(Collection<String> availableIds) {
        Set<String> available = new LinkedHashSet<>(availableIds);
        available.removeAll(HIDDEN_CATEGORIES);
        List<String> result = new ArrayList<>();
        if (!initiationIds(available).isEmpty()) result.add(INITIATION_GROUP);
        if (!engineeringIds(available).isEmpty()) result.add(ENGINEERING_GROUP);
        for (String id : ROOT_CATEGORIES) if (available.contains(id)) result.add(id);
        for (String id : available) {
            if (!ROOT_CATEGORIES.contains(id) && !ENGINEERING.contains(id) && !INITIATION.contains(id)) result.add(id);
        }
        return Collections.unmodifiableList(result);
    }

    public static String subtitle(String id) {
        switch (id) {
            case INITIATION_GROUP: return "Воспламенители, детонаторы, взрыватели, шнуры, провода и приборы";
            case ENGINEERING_GROUP: return "Мины, заряды и самодельные устройства";
            case "mines-antipersonnel": return "Противопехотные мины и их разновидности";
            case "mines-antitank": return "Противотанковые мины разных стран";
            case "mines-antibottom": return "Противоднищевые мины: страны и обозначения";
            case "mines-antivehicle": return "Противотранспортные и специальные транспортные мины";
            case "mines-naval": return "Морские мины: страны и обозначения";
            case "mines-anchored": return "Якорные морские мины разных стран";
            case "mines-antiland": return "Противодесантные и противодиверсионные мины";
            case "mines-special": return "Специальные и сигнальные мины";
            case "charges": return "Инженерные заряды: виды и справочные описания";
            case "ied": return "Самодельные взрывные устройства: внешний вид и сведения из источников";
            case "engineering": return "Термины, классификация и общие сведения";
            case "ignition-electric": return "Разновидности электрических воспламенителей";
            case "detonators-caps": return "Капсюли-детонаторы: обозначения и модели";
            case "primers": return "Запалы разных стран и семейств";
            case "detonators-electric": return "Электродетонаторы: модели и справочные сведения";
            case "fuse-cord": return "Огнепроводные шнуры: виды и обозначения";
            case "detonating-cord": return "Детонирующие шнуры разных производителей";
            case "sapper-wires": return "Сапёрные провода: обозначения и разновидности";
            case "blasting-machines": return "Подрывные машинки: модели и справочные описания";
            case "measuring-instruments": return "Проверочные и измерительные приборы: виды и обозначения";
            case "ignition-tubes": return "Зажигательные трубки: разновидности и описание";
            case "mine-fuzes": return "Минные взрыватели: страны и модели";
            case "grenade-fuzes": return "Гранатные взрыватели и запалы";
            case "artillery-fuzes": return "Взрыватели артиллерийских боеприпасов";
            case "detonators-nonelectric": return "Неэлектрические детонаторы: справочные сведения";
            case "detonators-electronic": return "Электронные детонаторы: обозначения и разновидности";
            case "fuzes": return "Другие взрыватели, группы обозначений и общие сведения";
            case "grenades": return "Ручные и гранатомётные гранаты";
            case "mortars": return "Миномётные выстрелы: внешний вид, маркировка и калибры";
            case "artillery": return "Артиллерийские боеприпасы и их разновидности";
            case "cannon-ammunition": return "Малокалиберные пушечные боеприпасы и выстрелы";
            case "rockets-recoilless": return "Реактивные и безоткатные боеприпасы";
            case "air-munitions": return "Авиационные боеприпасы и средства поражения";
            case "submunitions": return "Суббоеприпасы и кассетные элементы";
            case "audit-candidates": return "Неподтверждённые обозначения — не использовать как установленный факт";
            case "reference": return "Справочные материалы, термины и работа с источниками";
            default: return "Описание, изображения и справочные сведения";
        }
    }
}
