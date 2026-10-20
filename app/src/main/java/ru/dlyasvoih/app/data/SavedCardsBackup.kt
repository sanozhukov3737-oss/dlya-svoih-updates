package ru.dlyasvoih.app.data

import ru.dlyasvoih.app.data.local.ContinueReading

/**
 * A backup of favorites and reading progress, and its plain-text codec.
 *
 * Android only carries these two tables forward across a reinstall when the new APK is signed
 * with the same key (see GuideDatabase and README_RU.md). Losing the signing key therefore loses
 * both tables for good, with nothing in the app to fall back on. This format lets a person save
 * that list outside the app - to a file, or as shared plain text through any local channel with no
 * network involved - and restore it later on any install, by card id, independent of signing.
 *
 * The format deliberately avoids org.json: that class is stubbed out in Android's unit-test jar,
 * so a codec built on it can only be checked by an instrumented test, never by a fast host one.
 * This codec needs nothing Android-specific, so it is covered by SavedCardsCodecTest instead.
 */
object SavedCardsCodec {
    const val FORMAT_VERSION = 1
    private const val HEADER = "DLYA_SVOIH_SAVED_CARDS v$FORMAT_VERSION"
    private const val FAVORITES_SECTION = "[favorites]"
    private const val READING_SECTION = "[reading]"

    fun encode(export: SavedCardsExport, exportedAt: String): String = buildString {
        appendLine(HEADER)
        appendLine("# ДЛЯ СВОИХ — резервная копия избранного и недавних")
        appendLine("# Строка вида id<TAB>заголовок. Заголовок нужен только для чтения человеком")
        appendLine("# и при восстановлении не используется.")
        appendLine("# exportedAt=$exportedAt")
        appendLine()
        appendLine(FAVORITES_SECTION)
        for (item in export.favorites) appendLine("${item.cardId}\t${item.title}")
        appendLine()
        appendLine(READING_SECTION)
        for (item in export.reading) appendLine("${item.cardId}\t${item.title}")
    }

    fun decode(text: String): SavedCardsExport {
        val lines = text.lineSequence().map { it.trim() }
            .filterNot { it.isEmpty() || it.startsWith("#") }.toList()
        require(lines.isNotEmpty() && lines.first().startsWith("DLYA_SVOIH_SAVED_CARDS")) {
            "Это не файл резервной копии избранного"
        }
        require(lines.first() == HEADER) { "Неподдерживаемая версия файла резервной копии" }
        val favorites = mutableListOf<ContinueReading>()
        val reading = mutableListOf<ContinueReading>()
        var current: MutableList<ContinueReading>? = null
        for (line in lines.drop(1)) {
            when (line) {
                FAVORITES_SECTION -> current = favorites
                READING_SECTION -> current = reading
                else -> {
                    val target = current ?: continue
                    val tab = line.indexOf('\t')
                    val id = if (tab >= 0) line.substring(0, tab) else line
                    val title = if (tab >= 0) line.substring(tab + 1) else id
                    if (id.isNotBlank()) target += ContinueReading(id, title)
                }
            }
        }
        return SavedCardsExport(favorites, reading)
    }
}

data class SavedCardsExport(val favorites: List<ContinueReading>, val reading: List<ContinueReading>) {
    val isEmpty: Boolean get() = favorites.isEmpty() && reading.isEmpty()
}

data class SavedCardsImportResult(
    val favoritesRestored: Int, val favoritesMissing: List<String>,
    val readingRestored: Int, val readingMissing: List<String>
) {
    val hasMissing: Boolean get() = favoritesMissing.isNotEmpty() || readingMissing.isNotEmpty()
}
