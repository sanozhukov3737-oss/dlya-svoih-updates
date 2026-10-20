package ru.dlyasvoih.app.data.update

import org.json.JSONObject
import java.io.File

data class RemoteCatalog(val version: Long, val url: String, val bytes: Long, val sha256: String,
    val changes: String, val minAppCode: Int)

sealed interface RemoteUpdateState {
    data object Idle : RemoteUpdateState
    data object Checking : RemoteUpdateState
    data class Available(val catalog: RemoteCatalog) : RemoteUpdateState
    data class Current(val version: Long) : RemoteUpdateState
    data class Downloading(val bytes: Long, val total: Long) : RemoteUpdateState
    data object Installing : RemoteUpdateState
    data object NeedsAppUpdate : RemoteUpdateState
    data class Error(val message: String, val catalog: RemoteCatalog? = null) : RemoteUpdateState
    val busy: Boolean get() = this is Checking || this is Downloading || this is Installing
}

class RemoteCatalogSource(private val cache: File, private val files: RemoteFiles = RemoteFiles()) {
    fun check(address: String): RemoteCatalog = decode(files.text(address))

    companion object {
        fun decode(text: String): RemoteCatalog {
            require(text.toByteArray(Charsets.UTF_8).size <= 64 * 1024) { "Слишком большое описание обновления" }
            val json = JSONObject(text)
            fun number(name: String, default: Long? = null): Long = when (val value = json.opt(name)) {
                is Int -> value.toLong()
                is Long -> value
                null -> default ?: throw IllegalArgumentException("Не указан параметр $name")
                else -> throw IllegalArgumentException("Некорректный параметр $name")
            }
            require(number("formatVersion") == 1L) { "Неподдерживаемый формат обновлений" }
            val minimum = number("minAppCode", 1)
            require(minimum in 1..Int.MAX_VALUE.toLong()) { "Некорректная версия приложения" }
            val changes = json.opt("changes") ?: ""
            require(changes is String && changes.length <= 5000) { "Некорректное описание изменений" }
            val offer = RemoteCatalog(number("contentVersion"), json.getString("url"),
                number("bytes"), json.getString("sha256").lowercase(), changes, minimum.toInt())
            RemoteFiles.httpsUrl(offer.url)
            require(offer.version > 0 && offer.bytes in 1..PackFiles.MAX_ARCHIVE &&
                offer.sha256.matches(Regex("[a-f0-9]{64}"))) { "Некорректное описание обновления" }
            return offer
        }

        fun encode(offer: RemoteCatalog): String = JSONObject().put("formatVersion", 1)
            .put("contentVersion", offer.version).put("url", offer.url).put("bytes", offer.bytes)
            .put("sha256", offer.sha256).put("changes", offer.changes).put("minAppCode", offer.minAppCode).toString()
    }

    fun download(offer: RemoteCatalog, progress: (Long) -> Unit): File {
        val directory = File(cache, "remote-catalog")
        kotlin.check(directory.isDirectory || directory.mkdirs()) { "Не удалось подготовить скачивание" }
        return files.download(offer.url, File(directory, "catalog.zip"), offer.bytes, offer.sha256) { progress(it) }
    }
}
