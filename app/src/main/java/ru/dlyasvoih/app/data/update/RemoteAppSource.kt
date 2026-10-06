package ru.dlyasvoih.app.data.update

import org.json.JSONObject
import java.io.File

data class RemoteApp(val versionCode: Int, val versionName: String, val packageName: String,
    val minSdk: Int, val url: String, val bytes: Long, val sha256: String,
    val signerSha256: String, val changes: String)

sealed interface AppUpdateState {
    data object Idle : AppUpdateState
    data object Checking : AppUpdateState
    data object NotPublished : AppUpdateState
    data object Current : AppUpdateState
    data class Available(val app: RemoteApp) : AppUpdateState
    data class Downloading(val bytes: Long, val total: Long) : AppUpdateState
    data object Verifying : AppUpdateState
    data class Ready(val app: RemoteApp, val file: File) : AppUpdateState
    data class Unsupported(val minSdk: Int) : AppUpdateState
    data class Error(val message: String, val app: RemoteApp? = null) : AppUpdateState
    val busy: Boolean get() = this is Checking || this is Downloading || this is Verifying
}

class RemoteAppSource(private val cache: File, private val files: RemoteFiles = RemoteFiles()) {
    fun check(): RemoteApp? = decode(files.text(FEED_URL))

    fun download(app: RemoteApp, progress: (Long) -> Unit): File {
        val directory = File(cache, "remote-apk")
        kotlin.check(directory.isDirectory || directory.mkdirs()) { "Не удалось подготовить скачивание APK" }
        return files.download(app.url, File(directory, "update.apk"), app.bytes, app.sha256) { progress(it) }
    }

    fun cachedFile(): File = File(cache, "remote-apk/update.apk")

    companion object {
        const val FEED_URL = "https://github.com/sanozhukov3737-oss/dlya-svoih-updates/releases/latest/download/latest.json"

        fun decode(text: String): RemoteApp? {
            require(text.toByteArray(Charsets.UTF_8).size <= 64 * 1024) { "Слишком большое описание обновления" }
            val root = JSONObject(text)
            require(root.opt("formatVersion") == 1) { "Неподдерживаемый формат обновления" }
            if (!root.has("app")) return null
            val json = root.getJSONObject("app")
            fun number(name: String): Long = when (val value = json.opt(name)) {
                is Int -> value.toLong()
                is Long -> value
                else -> throw IllegalArgumentException("Некорректный параметр APK: $name")
            }
            fun string(name: String, maximum: Int): String {
                val value = json.opt(name)
                require(value is String && value.isNotBlank() && value.length <= maximum) { "Некорректный параметр APK: $name" }
                return value
            }
            require(number("formatVersion") == 1L) { "Неподдерживаемый формат APK" }
            val code = number("versionCode")
            val sdk = number("minSdk")
            val size = number("bytes")
            require(code in 1..Int.MAX_VALUE.toLong() && sdk in 26..Int.MAX_VALUE.toLong() && size in 1..PackFiles.MAX_ARCHIVE) {
                "Некорректная версия или размер APK"
            }
            val url = string("url", 2048)
            RemoteFiles.httpsUrl(url)
            val hash = string("sha256", 64).lowercase()
            val signer = string("signerSha256", 64).lowercase()
            require(hash.matches(Regex("[a-f0-9]{64}")) && signer.matches(Regex("[a-f0-9]{64}"))) { "Некорректный хеш или сертификат APK" }
            val changes = json.opt("changes") ?: ""
            require(changes is String && changes.length <= 5000) { "Некорректное описание изменений APK" }
            return RemoteApp(code.toInt(), string("versionName", 80), string("packageName", 200), sdk.toInt(),
                url, size, hash, signer, changes)
        }

        fun encode(app: RemoteApp): String = JSONObject().put("formatVersion", 1).put("app", JSONObject()
            .put("formatVersion", 1).put("versionCode", app.versionCode).put("versionName", app.versionName)
            .put("packageName", app.packageName).put("minSdk", app.minSdk).put("url", app.url)
            .put("bytes", app.bytes).put("sha256", app.sha256).put("signerSha256", app.signerSha256)
            .put("changes", app.changes)).toString()
    }
}
