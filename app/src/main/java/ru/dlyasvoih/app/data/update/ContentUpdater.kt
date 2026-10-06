package ru.dlyasvoih.app.data.update

import android.content.Context
import android.database.Cursor
import android.database.sqlite.SQLiteDatabase
import android.graphics.BitmapFactory
import android.system.Os
import android.system.OsConstants
import androidx.room.withTransaction
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import org.json.JSONObject
import ru.dlyasvoih.app.data.SearchQuery
import ru.dlyasvoih.app.data.local.*
import java.io.File
import java.io.FileOutputStream
import java.io.InputStream

/** Offline, versioned imports. A failed import never replaces the live database file. */
class ContentUpdater(private val context: Context, private val db: GuideDatabase) {
    private val mutex = Mutex()
    private val dao = db.guideDao()
    private val staging = File(context.cacheDir, "content-import")
    private val packs = File(context.filesDir, "packs")

    suspend fun initialize() = withContext(Dispatchers.IO) { mutex.withLock {
        staging.deleteRecursively()
        val bundledVersion = context.assets.open("database/content-version.txt").bufferedReader().use { it.readText().trim().toLong() }
        val installedVersion = dao.metadata("content_version")?.toLongOrNull() ?: 0L
        // Normal startup reads only the version marker, never copies the whole bundled database.
        if (bundledVersion > installedVersion) {
            check(staging.mkdirs())
            val seed = copySeed()
            readDatabase(seed).use { incoming ->
                require(version(incoming) == bundledVersion) { "Версия встроенного каталога не совпала" }
                validate(incoming, seed, null)
                apply(incoming, "")
            }
        }
        // Run only at startup, when no gallery can still hold references to an older pack.
        if (packs.isDirectory) {
            val referenced = dao.usedMedia().map { it.split('/')[1] }.toSet()
            packs.listFiles()?.filter { it.isDirectory && it.name !in referenced }?.forEach { it.deleteRecursively() }
        }
        staging.deleteRecursively()
    } }

    suspend fun importPack(input: InputStream, expectedVersion: Long? = null): Long = withContext(Dispatchers.IO) { mutex.withLock {
        staging.deleteRecursively()
        check(staging.mkdirs())
        try {
            val archive = File(staging, "input.zip")
            input.use { source -> archive.outputStream().use { PackFiles.copyLimited(source, it, PackFiles.MAX_ARCHIVE) } }
            val digest = PackFiles.sha256(archive)
            val extracted = File(staging, "extracted")
            val entries = PackFiles.extract(archive, extracted)
            val manifest = JSONObject(File(extracted, "manifest.json").readText())
            require(manifest.getInt("formatVersion") == 1) { "Неподдерживаемый формат пакета" }
            val records = manifest.getJSONArray("files")
            require(records.length() == entries.size - 1) { "Неполный список файлов" }
            val declared = mutableSetOf("manifest.json")
            for (i in 0 until records.length()) {
                val item = records.getJSONObject(i)
                val name = item.getString("path")
                require(name in entries && declared.add(name)) { "Повтор файла в пакете" }
                val file = File(extracted, name)
                require(file.length() == item.getLong("bytes") && PackFiles.sha256(file) == item.getString("sha256")) {
                    "Пакет повреждён: контрольная сумма не совпала"
                }
            }
            val seed = copySeed()
            readDatabase(File(extracted, "guide.db")).use { incoming ->
                validate(incoming, seed, extracted)
                val next = version(incoming)
                require(expectedVersion == null || next == expectedVersion) { "Версия скачанного каталога не совпала с объявленной" }
                require(next == manifest.getLong("contentVersion")) { "Версии пакета и базы различаются" }
                require(next > (dao.metadata("content_version")?.toLongOrNull() ?: 0L)) { "Эта версия каталога уже установлена или устарела" }
                val promoted = File(packs, digest)
                // An interrupted import can leave an unreferenced directory. Replace it on retry.
                require(dao.usedMedia().none { it.startsWith("packs/$digest/") }) { "Этот пакет уже используется" }
                if (promoted.exists()) check(promoted.deleteRecursively())
                check(promoted.mkdirs()) { "Не удалось подготовить изображения" }
                for (name in listOf("images", "thumbs")) {
                    val source = File(extracted, name)
                    if (source.exists()) {
                        check(source.renameTo(File(promoted, name))) { "Не удалось сохранить изображения" }
                        syncDirectory(File(promoted, name))
                    }
                }
                syncDirectory(promoted)
                syncDirectory(packs)
                apply(incoming, "packs/$digest/")
                next
            }
        } finally { staging.deleteRecursively() }
    } }

    private fun copySeed(): File = File(staging, "seed.db").also { file ->
        context.assets.open("database/guide-v29.db").use { input ->
            FileOutputStream(file).use { output ->
                input.copyTo(output)
                output.fd.sync()
            }
        }
        require(file.length() >= 4096L) { "Встроенная база скопирована не полностью" }
    }

    private fun readDatabase(file: File): SQLiteDatabase = SQLiteDatabase.openDatabase(file.path, null,
        SQLiteDatabase.OPEN_READONLY or SQLiteDatabase.NO_LOCALIZED_COLLATORS)

    private fun version(source: SQLiteDatabase): Long = source.rawQuery(
        "SELECT value FROM metadata WHERE `key` = 'content_version'", null).use {
        require(it.moveToFirst()) { "Не указана версия каталога" }
        it.getString(0).toLong().also { number -> require(number > 0) }
    }

    private fun schema(source: SQLiteDatabase): List<String> = source.rawQuery(
        "SELECT type, name, sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name", null).use {
        buildList { while (it.moveToNext()) add("${it.getString(0)}:${it.getString(1)}:${it.getString(2)}") }
    }

    private fun count(source: SQLiteDatabase, table: String): Long = source.rawQuery("SELECT COUNT(*) FROM $table", null)
        .use { it.moveToFirst(); it.getLong(0) }

    private fun validate(source: SQLiteDatabase, seed: File, media: File?) {
        readDatabase(seed).use { require(source.version == 3 && schema(source) == schema(it)) { "Несовместимая схема каталога" } }
        // Do not run integrity_check or quick_check on the phone. Both depend on the SQLite/FTS
        // version shipped by the device and can reject a valid database produced by a newer
        // desktop SQLite. The schema comparison and exhaustive reads below touch every catalog
        // row; malformed pages still fail as SQLiteExceptions, while logical damage is rejected
        // by the foreign-key, range, identifier and media checks.
        source.rawQuery("PRAGMA foreign_key_check", null).use { require(!it.moveToFirst()) { "Нарушены связи карточек" } }
        require(count(source, "cards") in 1..50_000 && count(source, "countries") in 1..256 &&
            count(source, "categories") in 1..512 && count(source, "images") <= 20_000 && count(source, "sources") <= 100_000 &&
            count(source, "card_countries") <= 200_000 && count(source, "metadata") <= 16 &&
            count(source, "favorites") == 0L && count(source, "reading") == 0L) { "Недопустимый состав пакета" }
        source.rawQuery("SELECT id, name FROM countries", null).use { rows ->
            var hasRussia = false
            while (rows.moveToNext()) { safeId(rows.getString(0)); limited(rows.getString(1), 120); hasRussia = hasRussia || rows.getString(0) == "ru" }
            require(hasRussia) { "В каталоге отсутствует Россия" }
        }
        source.rawQuery("SELECT id, section, title FROM categories", null).use { rows ->
            while (rows.moveToNext()) { safeId(rows.getString(0)); section(rows.getString(1)); limited(rows.getString(2), 200) }
        }
        source.rawQuery("SELECT c.id FROM cards c JOIN categories k ON c.categoryId = k.id WHERE c.section != k.section LIMIT 1", null)
            .use { require(!it.moveToFirst()) { "Раздел карточки не совпал с категорией" } }
        source.rawQuery("SELECT * FROM cards", null).use { rows -> while (rows.moveToNext()) {
            val card = card(rows, "")
            safeId(card.id); require(card.rowId > 0 && !card.archived); section(card.section)
            limited(card.title, 200); limited(card.summary, 600); limited(card.body, 100_000); limited(card.tags, 2000, true)
            require(card.sortTitle == SearchQuery.normalize(card.title)) { "Неверная сортировка" }
            val legacySearch = SearchQuery.normalize(listOf(card.title, card.summary, card.body, card.tags.replace(" · ", " ")).joinToString(" "))
            val readerSearch = SearchQuery.normalize(listOf(card.title, card.summary,
                ru.dlyasvoih.app.ui.content.ReaderContent.searchableBody(card.body), card.tags.replace(" · ", " ")).joinToString(" "))
            require(card.searchText == legacySearch || card.searchText == readerSearch) {
                "Неверный поисковый текст"
            }
            require(card.contentStatus in setOf("demo", "medical_review_required", "reviewed", "source_only", "candidate")) {
                "Некорректный статус карточки"
            }
            card.reviewedAt?.let { limited(it, 40) }
            limited(card.modelStatus, 40)
            require(card.sourceGrade in setOf("A", "B", "legacy")) { "Некорректный уровень источника" }
            card.verifiedAt?.let { limited(it, 40) }
            card.thumbnailPath?.let { verifyImage(it, media, 256, null, null) }
        } }
        source.rawQuery("SELECT * FROM images", null).use { rows -> while (rows.moveToNext()) {
            val image = image(rows, "")
            safeId(image.id); limited(image.caption, 600)
            require(image.position in 0..11) { "Недопустимая позиция изображения ${image.id}: ${image.position}" }
            verifyImage(image.localPath, media, 1600, image.width, image.height)
        } }
        source.rawQuery("SELECT cardId FROM images GROUP BY cardId HAVING COUNT(*) > 12", null).use { require(!it.moveToFirst()) }
        source.rawQuery("SELECT id, title, url, accessedAt FROM sources", null).use { rows -> while (rows.moveToNext()) {
            safeId(rows.getString(0)); limited(rows.getString(1), 500)
            if (!rows.isNull(2)) require(rows.getString(2).length <= 2048 && rows.getString(2).startsWith("https://"))
            if (!rows.isNull(3)) limited(rows.getString(3), 40)
        } }
        // Incoming FTS shadow-table contents are deliberately never copied. Live triggers rebuild the index.
    }

    private fun verifyImage(path: String, media: File?, limit: Int, width: Int?, height: Int?) {
        require(PackFiles.isMediaPath(path)) { "Недопустимый путь изображения" }
        require(if (limit == 256) path.startsWith("thumbs/") else path.startsWith("images/"))
        val options = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        if (media == null) context.assets.open(path).use { BitmapFactory.decodeStream(it, null, options) }
        else {
            val file = File(media, path)
            require(file.isFile && file.length() <= 4L * 1024 * 1024) { "Изображение отсутствует" }
            BitmapFactory.decodeFile(file.path, options)
        }
        require(options.outWidth in 1..limit && options.outHeight in 1..limit) { "Неверный размер изображения" }
        require((width == null || width == options.outWidth) && (height == null || height == options.outHeight)) { "Размер изображения не совпал с описанием" }
    }

    private fun safeId(value: String) { require(value.matches(Regex("[a-z0-9][a-z0-9-]{0,95}"))) { "Некорректный идентификатор" } }
    private fun section(value: String) { require(value in setOf("AMMUNITION", "ATGM", "SVO", "MEDICINE")) }
    private fun limited(value: String, limit: Int, empty: Boolean = false) { require(value.length <= limit && (empty || value.isNotBlank())) { "Некорректный текст" } }

    // Upsert never uses REPLACE, which would cascade-delete favorites and reading progress.
    private suspend fun apply(source: SQLiteDatabase, mediaPrefix: String) = db.withTransaction {
        val next = version(source)
        require(next > (dao.metadata("content_version")?.toLongOrNull() ?: 0L))
        source.rawQuery("SELECT * FROM countries", null).use { rows ->
            val values = mutableListOf<CountryEntity>()
            while (rows.moveToNext()) values += CountryEntity(rows.text("id"), rows.text("name"), rows.number("sortOrder"))
            dao.putCountries(values)
        }
        source.rawQuery("SELECT * FROM categories", null).use { rows ->
            val values = mutableListOf<CategoryEntity>()
            while (rows.moveToNext()) values += CategoryEntity(rows.text("id"), rows.text("section"), rows.text("title"), rows.number("sortOrder"))
            dao.putCategories(values)
        }
        dao.archiveCards()
        source.rawQuery("SELECT * FROM cards ORDER BY rowid", null).use { rows -> while (rows.moveToNext()) {
            val value = card(rows, mediaPrefix)
            require(dao.idForRow(value.rowId).let { it == null || it == value.id } &&
                dao.rowForId(value.id).let { it == null || it == value.rowId }) { "Изменён постоянный идентификатор карточки" }
            dao.putCard(value)
            dao.clearImages(value.id); dao.clearSources(value.id); dao.clearCardCountries(value.id)
        } }
        source.rawQuery("SELECT * FROM images ORDER BY id", null).use { rows ->
            val batch = mutableListOf<ImageEntity>()
            while (rows.moveToNext()) {
                batch += image(rows, mediaPrefix)
                if (batch.size == 100) { dao.putImages(batch); batch.clear() }
            }
            if (batch.isNotEmpty()) dao.putImages(batch)
        }
        source.rawQuery("SELECT * FROM sources ORDER BY id", null).use { rows ->
            val batch = mutableListOf<SourceEntity>()
            while (rows.moveToNext()) {
                batch += SourceEntity(rows.text("id"), rows.text("cardId"), rows.text("title"), rows.optional("url"), rows.optional("accessedAt"))
                if (batch.size == 100) { dao.putSources(batch); batch.clear() }
            }
            if (batch.isNotEmpty()) dao.putSources(batch)
        }
        source.rawQuery("SELECT * FROM card_countries", null).use { rows ->
            val batch = mutableListOf<CardCountryEntity>()
            while (rows.moveToNext()) {
                batch += CardCountryEntity(rows.text("cardId"), rows.text("countryId"))
                if (batch.size == 100) { dao.putCardCountries(batch); batch.clear() }
            }
            if (batch.isNotEmpty()) dao.putCardCountries(batch)
        }
        dao.pruneArchived()
        dao.putMetadata(MetadataEntity("content_version", next.toString()))
    }

    private fun card(row: Cursor, prefix: String) = CardEntity(row.getLong(row.getColumnIndexOrThrow("rowid")),
        row.text("id"), row.text("section"), row.text("categoryId"), row.text("title"), row.text("summary"), row.text("body"),
        row.text("tags"), row.text("sortTitle"), row.text("searchText"), row.optional("thumbnailPath")?.let { prefix + it },
        row.text("contentStatus"), row.optional("reviewedAt"), row.number("archived") != 0,
        row.text("modelStatus"), row.text("sourceGrade"), row.optional("verifiedAt"))
    private fun image(row: Cursor, prefix: String) = ImageEntity(row.text("id"), row.text("cardId"), prefix + row.text("localPath"),
        row.text("caption"), row.number("width"), row.number("height"), row.number("position"))
    private fun Cursor.text(name: String) = getString(getColumnIndexOrThrow(name)) ?: error("Missing $name")
    private fun Cursor.optional(name: String): String? = getString(getColumnIndexOrThrow(name))
    private fun Cursor.number(name: String) = getInt(getColumnIndexOrThrow(name))
    private fun syncDirectory(file: File) {
        check(file.isDirectory) { "Directory expected: ${file.path}" }
        val fd = Os.open(file.path, OsConstants.O_RDONLY, 0)
        try { Os.fsync(fd) } finally { Os.close(fd) }
    }
}
