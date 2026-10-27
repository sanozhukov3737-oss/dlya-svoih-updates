package ru.dlyasvoih.app.ui.screens

import android.content.Context
import android.net.Uri
import android.webkit.WebResourceResponse
import org.json.JSONObject
import org.json.JSONArray
import java.util.Locale
import java.io.ByteArrayInputStream

internal data class OfflineModel(
    val id: String, val file: String, val title: String, val cardIds: Set<String>,
    val subtitle: String, val author: String, val source: String,
    val license: String, val licenseUrl: String, val displayNote: String
)

internal object OfflineModelFiles {
    const val CARD_ID = "ref-v8-tm-46"
    const val ENTRY_URL = "https://appassets.androidplatform.net/assets/viewer3d/index.html"
    @Volatile private var cached: List<OfflineModel>? = null
    @Volatile private var cardIndex: Set<String>? = null

    fun hasForCard(context: Context, cardId: String): Boolean {
        val ids = cardIndex ?: synchronized(this) {
            cardIndex ?: context.assets.open("viewer3d/card-index.json").bufferedReader().use {
                val array = JSONArray(it.readText())
                (0 until array.length()).map { index -> array.getString(index) }.toSet()
            }.also { cardIndex = it }
        }
        return cardId in ids
    }

    fun normalizeSearch(value: String): String = value.lowercase(Locale.ROOT).replace('ё', 'е')
        .filter { it.isLetterOrDigit() }

    fun search(models: List<OfflineModel>, query: String): List<OfflineModel> {
        val needle = normalizeSearch(query)
        return if (needle.isEmpty()) models else models.filter {
            normalizeSearch(it.title).contains(needle) || normalizeSearch(it.id).contains(needle)
        }
    }

    fun models(context: Context): List<OfflineModel> = cached ?: synchronized(this) {
        cached ?: context.assets.open("viewer3d/models.json").bufferedReader().use { reader ->
            val entries = JSONObject(reader.readText()).getJSONArray("models")
            List(entries.length()) { index ->
                val item = entries.getJSONObject(index)
                val ids = item.getJSONArray("cardIds")
                OfflineModel(item.getString("id"), item.getString("file"), item.getString("title"),
                    (0 until ids.length()).map { ids.getString(it) }.toSet(),
                    item.getString("subtitle"), item.getString("author"), item.getString("source"),
                    item.getString("license"), item.optString("licenseUrl"), item.getString("displayNote"))
            }.also { cached = it }
        }
    }

    fun forCard(context: Context, cardId: String): OfflineModel? = models(context).firstOrNull { cardId in it.cardIds }
    fun entryUrl(modelId: String): String = ENTRY_URL + "#" + modelId
    fun isEntry(context: Context, uri: Uri): Boolean = uri.toString() == ENTRY_URL ||
        models(context).any { uri.toString() == entryUrl(it.id) }

    fun response(context: Context, uri: Uri): WebResourceResponse {
        val prefix = "/assets/viewer3d/"
        val path = uri.encodedPath.orEmpty()
        val name = path.removePrefix(prefix)
        val mime = when (name) {
            "index.html" -> "text/html"
            "viewer.bundle.js" -> "text/javascript"
            "models.json", "model-credits.json" -> "application/json"
            else -> if (models(context).any { it.file == name }) "model/gltf-binary" else null
        }
        if (uri.scheme != "https" || uri.host != "appassets.androidplatform.net" || uri.port != -1 ||
            uri.userInfo != null || uri.query != null || !path.startsWith(prefix) || mime == null) return blocked()
        return try {
            WebResourceResponse(mime, if (name.endsWith(".glb")) null else "UTF-8", 200, "OK",
                mapOf("Cache-Control" to "no-store", "X-Content-Type-Options" to "nosniff"),
                context.assets.open("viewer3d/$name"))
        } catch (_: Exception) { blocked() }
    }

    private fun blocked() = WebResourceResponse("text/plain", "UTF-8", 403, "Forbidden",
        emptyMap(), ByteArrayInputStream(byteArrayOf()))
}
