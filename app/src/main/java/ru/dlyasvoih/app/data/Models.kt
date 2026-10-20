package ru.dlyasvoih.app.data

enum class MainSection(val title: String, val subtitle: String, val mark: String) {
    AMMUNITION("Боеприпасы", "Категории и общие памятки", "◇"),
    ATGM("ПТРК", "Историческая и справочная информация", "◎"),
    SVO("СВО", "Хроника и проверка источников", "▦"),
    MEDICINE("Медицина", "Первая помощь", "+");

    companion object {
        fun fromId(id: String): MainSection? = entries.firstOrNull { it.name == id }
    }
}
