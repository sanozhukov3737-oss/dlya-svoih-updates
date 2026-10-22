package ru.dlyasvoih.app.ui.screens

import android.app.ActivityManager
import android.content.Context
import android.graphics.Bitmap
import android.os.Build
import android.util.Log
import androidx.compose.runtime.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.performTouchInput
import androidx.compose.ui.test.swipeLeft
import androidx.compose.ui.test.swipeRight
import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.ViewModelStore
import androidx.test.platform.app.InstrumentationRegistry
import coil3.SingletonImageLoader
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import ru.dlyasvoih.app.GuideApplication
import ru.dlyasvoih.app.diagnostics.PhotoProbe
import ru.dlyasvoih.app.ui.CardReaderState
import ru.dlyasvoih.app.ui.CardReaderViewModel
import ru.dlyasvoih.app.ui.theme.DlyaSvoihTheme
import java.io.File

class PhotoLoadDiagnosticsTest {
    @get:Rule val compose = createComposeRule()

    @Test fun firstPassAndReturnWithProductionImageSettings() {
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val context = instrumentation.targetContext
        val application = context.applicationContext as GuideApplication
        val out = File(context.filesDir, "photo-diagnostics").apply { mkdirs() }
        val report = JSONObject().put("passed", false).put("sdk", Build.VERSION.SDK_INT)
            .put("packageName", context.packageName).put("diagnosticDebugBuild", true)
            .put("sourceCommit", InstrumentationRegistry.getArguments().getString("sourceCommit"))
        val observations = JSONArray()
        val cacheSnapshots = JSONArray()
        val store = ViewModelStore()
        var shown by mutableStateOf(false)
        var compositionBatch by mutableIntStateOf(0)
        try {
            val manager = context.getSystemService(ActivityManager::class.java)
            val loader = SingletonImageLoader.get(context)
            val cache = requireNotNull(loader.memoryCache)
            report.put("memoryClassMiB", manager.memoryClass).put("isLowRamDevice", manager.isLowRamDevice)
                .put("cacheMaxBytes", cache.maxSize).put("diskCacheEnabled", loader.diskCache != null)
            assertEquals(197, runBlocking { application.repository.dao.metadata("content_version") }?.toInt())
            var vm: CardReaderViewModel? = null
            compose.runOnIdle {
                vm = ViewModelProvider(store, object : ViewModelProvider.Factory {
                    override fun <T : androidx.lifecycle.ViewModel> create(modelClass: Class<T>): T {
                        @Suppress("UNCHECKED_CAST")
                        return CardReaderViewModel(application.repository, SavedStateHandle(mapOf(
                            "section" to "AMMUNITION", "category" to "mines-antipersonnel"))) as T
                    }
                })[CardReaderViewModel::class.java]
            }
            val reader = requireNotNull(vm)
            compose.waitUntil(20_000) { reader.state.value is CardReaderState.Ready }
            val ready = reader.state.value as CardReaderState.Ready
            val cards = ready.cards.take(18)
            assertEquals(194, ready.ids.size)
            assertEquals(18, cards.size)
            val paths = cards.associate { card -> card.id to runBlocking {
                application.repository.dao.images(card.id).first().firstOrNull()?.localPath.orEmpty()
            } }
            assertTrue("At least 15 hero images required", paths.values.count { it.isNotEmpty() } >= 15)
            report.put("bookSize", ready.ids.size).put("cards", JSONArray(cards.map {
                JSONObject().put("id", it.id).put("heroPath", paths.getValue(it.id))
            }))
            compose.setContent {
                if (shown) key(compositionBatch) {
                    DlyaSvoihTheme(themeMode = 2) {
                        CardReaderScreen(reader, application.repository, {}, {}, {}, { _, _ -> })
                    }
                }
            }
            fun cacheSnapshot(label: String) {
                cacheSnapshots.put(JSONObject().put("batch", PhotoProbe.batch).put("label", label)
                    .put("sizeBytes", cache.size).put("maxBytes", cache.maxSize).put("keys", cache.keys.size))
            }
            fun photo(index: Int, leg: String, inputAt: Long) {
                val id = cards[index].id
                compose.waitUntil(10_000) { PhotoProbe.lastSettled == id }
                val settledObservedAt = PhotoProbe.now()
                val path = paths.getValue(id)
                if (path.isNotEmpty()) compose.waitUntil(10_000) { PhotoProbe.drawnAt(path) != null }
                observations.put(JSONObject().put("batch", PhotoProbe.batch).put("leg", leg)
                    .put("index", index).put("cardId", id).put("path", path).put("inputAtNs", inputAt)
                    .put("settledObservedAtNs", settledObservedAt)
                    .put("firstDrawAtNs", path.takeIf { it.isNotEmpty() }?.let { PhotoProbe.drawnAt(it) }))
            }
            fun screenshot(name: String) {
                val screenshot = requireNotNull(instrumentation.uiAutomation.takeScreenshot())
                File(out, "$name.png").outputStream().use { screenshot.compress(Bitmap.CompressFormat.PNG, 100, it) }
                screenshot.recycle()
            }
            for (batch in 1..3) {
                compose.runOnIdle { shown = false }
                compose.waitForIdle()
                compose.runOnIdle { cache.clear(); PhotoProbe.begin(batch); compositionBatch = batch }
                cacheSnapshot("cleared")
                PhotoProbe.phase = "open"
                val openedAt = PhotoProbe.record("input", mapOf("cardId" to cards.first().id))
                compose.runOnIdle { shown = true }
                photo(0, "open", openedAt)
                if (batch == 1) screenshot("first-open")
                for (index in 1 until cards.size) {
                    PhotoProbe.phase = "forward"
                    val at = PhotoProbe.record("input", mapOf("cardId" to cards[index].id, "index" to index))
                    compose.onNodeWithTag("card_reader").performTouchInput { swipeLeft(durationMillis = 280) }
                    photo(index, "forward", at)
                }
                cacheSnapshot("forward-end")
                if (batch == 1) screenshot("forward-end")
                for (index in cards.size - 2 downTo 0) {
                    PhotoProbe.phase = "return"
                    val at = PhotoProbe.record("input", mapOf("cardId" to cards[index].id, "index" to index))
                    compose.onNodeWithTag("card_reader").performTouchInput { swipeRight(durationMillis = 280) }
                    photo(index, "return", at)
                }
                cacheSnapshot("return-end")
                if (batch == 1) screenshot("returned")
                Log.i("PhotoDiag", "Batch $batch complete: 18 cards, 17 forward, 17 return")
            }
            report.put("passed", true)
        } catch (failure: Throwable) {
            report.put("failure", failure.toString())
            throw failure
        } finally {
            report.put("observations", observations).put("cacheSnapshots", cacheSnapshots)
                .put("events", PhotoProbe.eventJson())
            File(out, "raw.json").writeText(report.toString(2) + "\n")
            compose.runOnIdle { shown = false; store.clear() }
        }
    }
}
