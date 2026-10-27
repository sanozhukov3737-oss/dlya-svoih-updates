package ru.dlyasvoih.app.ui.screens

import android.content.Context
import android.graphics.Bitmap
import android.os.ParcelFileDescriptor
import android.webkit.WebView
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.key
import androidx.compose.runtime.mutableStateOf
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.test.core.app.ApplicationProvider
import androidx.test.platform.app.InstrumentationRegistry
import java.io.File
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicReference
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test

class Collection138RenderTest {
    @get:Rule val compose = createComposeRule()

    @Test fun everyModelRendersAndRotatesInAndroidWebView() {
        val context = ApplicationProvider.getApplicationContext<Context>()
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val arguments = InstrumentationRegistry.getArguments()
        val shard = arguments.getString("modelShard", "0").toInt()
        val shards = arguments.getString("modelShards", "1").toInt()
        val models = OfflineModelFiles.models(context).filterIndexed { i, _ -> i % shards == shard }
        assertTrue(models.isNotEmpty())
        val out = File(context.getExternalFilesDir(null), "collection138").apply { mkdirs() }
        val results = JSONArray()
        val selected = mutableStateOf(models.first().id)
        lateinit var viewer: WebView
        compose.setContent { MaterialTheme {
            key(selected.value) {
                OfflineModelDialog(modelId = selected.value, onViewerCreated = { viewer = it }, onDismiss = {})
            }
        } }
        fun evaluate(script: String): String {
            val result = AtomicReference<String>()
            val done = CountDownLatch(1)
            instrumentation.runOnMainSync { viewer.evaluateJavascript(script) { result.set(it); done.countDown() } }
            check(done.await(10, TimeUnit.SECONDS)) { "JavaScript callback timed out" }
            return result.get()
        }
        fun frame() {
            val done = CountDownLatch(1)
            instrumentation.runOnMainSync {
                viewer.postVisualStateCallback(System.nanoTime(), object : WebView.VisualStateCallback() {
                    override fun onComplete(id: Long) { done.countDown() }
                })
            }
            assertTrue("No composited Android frame", done.await(15, TimeUnit.SECONDS))
        }
        fun save(name: String): Bitmap {
            frame()
            val geometry = IntArray(4)
            instrumentation.runOnMainSync {
                viewer.getLocationOnScreen(geometry)
                geometry[2] = viewer.width; geometry[3] = viewer.height
            }
            val screenshot = instrumentation.uiAutomation.takeScreenshot()
            assertNotNull(screenshot)
            val crop = Bitmap.createBitmap(screenshot, geometry[0], geometry[1], geometry[2], geometry[3])
            File(out, name).outputStream().use { crop.compress(Bitmap.CompressFormat.PNG, 100, it) }
            screenshot.recycle()
            return crop
        }
        for (model in models) {
            compose.runOnIdle { selected.value = model.id }
            compose.waitForIdle()
            val deadline = System.currentTimeMillis() + 60_000
            var state = ""
            while (System.currentTimeMillis() < deadline) {
                state = evaluate("document.body && document.body.dataset.state")
                if (evaluate("document.body && document.body.dataset.model") == JSONObject.quote(model.id) &&
                    state in listOf("\"ready\"", "\"error\"")) break
                Thread.sleep(100)
            }
            assertEquals(model.id + ": " + evaluate("document.body.innerText"), "\"ready\"", state)
            assertEquals(JSONObject.quote(model.id), evaluate("document.body.dataset.model"))
            val triangles = evaluate("Number(document.querySelector('canvas').dataset.triangles)").toInt()
            assertTrue(model.id, triangles > 0)
            val extent = evaluate("Number(document.querySelector('canvas').dataset.homeExtent)").toDouble()
            assertTrue(model.id + ": model outside viewport", extent > 0.05 && extent <= .85)
            instrumentation.runOnMainSync {
                assertTrue(viewer.settings.blockNetworkLoads)
                assertFalse(viewer.settings.allowFileAccess)
            }
            val before = save(model.id + ".png")
            val p = IntArray(2)
            var width = 0; var height = 0
            instrumentation.runOnMainSync { viewer.getLocationOnScreen(p); width=viewer.width; height=viewer.height }
            val command = "input swipe ${p[0]+width/4} ${p[1]+height/2} ${p[0]+3*width/4} ${p[1]+height/2} 650"
            ParcelFileDescriptor.AutoCloseInputStream(instrumentation.uiAutomation.executeShellCommand(command)).use { it.readBytes() }
            Thread.sleep(250)
            val after = save(model.id + "-rotated.png")
            assertFalse(model.id + ": rotated view is unchanged", before.sameAs(after))
            before.recycle(); after.recycle()
            results.put(JSONObject().put("id",model.id).put("triangles",triangles).put("homeExtent",extent)
                .put("initial",model.id+".png").put("rotated",model.id+"-rotated.png").put("passed",true))
            File(out, "result.json").writeText(JSONObject().put("shard",shard).put("shards",shards)
                .put("models",results).toString(2))
        }
    }
}
