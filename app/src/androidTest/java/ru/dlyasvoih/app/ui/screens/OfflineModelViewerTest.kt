package ru.dlyasvoih.app.ui.screens

import android.content.Context
import android.net.Uri
import android.webkit.WebView
import androidx.compose.material3.MaterialTheme
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.test.core.app.ApplicationProvider
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import android.os.ParcelFileDescriptor
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicReference

class OfflineModelViewerTest {
    @get:Rule val compose = createComposeRule()

    @Test fun modelIsAttachedOnlyToItsExactCardAndDialogCloses() {
        compose.setContent {
            MaterialTheme {
                OfflineModelAction("ref-v8-tmn-46", true)
                OfflineModelAction(OfflineModelFiles.CARD_ID, true)
            }
        }
        compose.onAllNodesWithTag("open_offline_3d").assertCountEquals(1)
        compose.onNodeWithTag("offline_3d_dialog").assertDoesNotExist()
        compose.onNodeWithTag("open_offline_3d").performClick()
        compose.onNodeWithTag("offline_3d_dialog").assertIsDisplayed()
        compose.onNodeWithContentDescription("Назад").performClick()
        compose.onNodeWithTag("offline_3d_dialog").assertDoesNotExist()
    }

    @Test fun packagedModelActuallyRendersWithNetworkAccessDisabled() {
        lateinit var viewer: WebView
        compose.setContent { MaterialTheme(colorScheme = androidx.compose.material3.darkColorScheme()) { OfflineModelDialog(onViewerCreated = { viewer = it }, onDismiss = {}) } }
        compose.waitForIdle()
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        fun evaluate(script: String): String {
            val answer = AtomicReference<String>()
            val latch = CountDownLatch(1)
            instrumentation.runOnMainSync { viewer.evaluateJavascript(script) { answer.set(it); latch.countDown() } }
            check(latch.await(5, TimeUnit.SECONDS)) { "WebView JavaScript did not respond" }
            return answer.get()
        }
        val deadline = System.currentTimeMillis() + 30_000
        var state = ""
        while (System.currentTimeMillis() < deadline) {
            state = evaluate("document.body.dataset.state")
            if (state == "\"ready\"" || state == "\"error\"") break
            Thread.sleep(100)
        }
        assertEquals(evaluate("document.body.innerText"), "\"ready\"", state)
        assertTrue(evaluate("Number(document.querySelector('canvas').dataset.triangles)").toInt() > 1_000)
        assertTrue(evaluate("Number(document.querySelector('canvas').dataset.colors)").toInt() > 100)
        instrumentation.runOnMainSync {
            assertTrue(viewer.settings.blockNetworkLoads)
            assertFalse(viewer.settings.allowFileAccess)
            assertFalse(viewer.settings.allowContentAccess)
        }
        // Gradle uninstalls the test app afterwards, so keep proof outside its data.
        val visualFrame = CountDownLatch(1)
        instrumentation.runOnMainSync {
            viewer.postVisualStateCallback(1L, object : WebView.VisualStateCallback() {
                override fun onComplete(requestId: Long) { visualFrame.countDown() }
            })
        }
        assertTrue("WebView did not produce a composited frame", visualFrame.await(10, TimeUnit.SECONDS))
        compose.waitForIdle()
        Thread.sleep(750)
        assertEquals("true", evaluate("document.getElementById('status').hidden"))
        val descriptor = instrumentation.uiAutomation.executeShellCommand(
            "screencap -p /data/local/tmp/offline-model-tm46.png")
        ParcelFileDescriptor.AutoCloseInputStream(descriptor).use { it.readBytes() }
    }

    @Test fun unknownAssetsRemoteAddressesAndTraversalAreBlocked() {
        val context = ApplicationProvider.getApplicationContext<Context>()
        val valid = OfflineModelFiles.response(context, Uri.parse(OfflineModelFiles.ENTRY_URL))
        assertEquals(200, valid.statusCode)
        valid.data.close()
        for (address in listOf("https://example.com/assets/viewer3d/index.html",
            "http://appassets.androidplatform.net/assets/viewer3d/index.html",
            "https://appassets.androidplatform.net/assets/viewer3d/../../database/guide-v29.db",
            "https://appassets.androidplatform.net/assets/viewer3d/%2e%2e/index.html",
            OfflineModelFiles.ENTRY_URL + "?remote=true", "file:///android_asset/viewer3d/index.html")) {
            val blocked = OfflineModelFiles.response(context, Uri.parse(address))
            assertEquals(address, 403, blocked.statusCode)
            blocked.data.close()
        }
    }
}
