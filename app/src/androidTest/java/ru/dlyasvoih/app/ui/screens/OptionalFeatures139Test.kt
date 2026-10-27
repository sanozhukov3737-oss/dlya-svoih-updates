package ru.dlyasvoih.app.ui.screens

import android.app.Activity
import android.app.NotificationManager
import android.app.job.JobScheduler
import android.content.Context
import android.content.ContextWrapper
import android.content.Intent
import android.graphics.Bitmap
import android.os.ParcelFileDescriptor
import android.webkit.WebView
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.mutableStateOf
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.test.core.app.ApplicationProvider
import androidx.test.platform.app.InstrumentationRegistry
import androidx.test.runner.lifecycle.ActivityLifecycleMonitorRegistry
import androidx.test.runner.lifecycle.Stage
import kotlinx.coroutines.*
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import ru.dlyasvoih.app.GuideApplication
import ru.dlyasvoih.app.MainActivity
import ru.dlyasvoih.app.data.models.ModelPackPhase
import ru.dlyasvoih.app.data.update.*
import java.io.File
import java.io.IOException
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicReference

class OptionalFeatures139Test {
    @get:Rule val compose = createComposeRule()
    private val context get() = ApplicationProvider.getApplicationContext<Context>()
    private val instrumentation get() = InstrumentationRegistry.getInstrumentation()
    private val out get() = File(context.getExternalFilesDir(null), "features139").apply { mkdirs() }
    private fun shell(command: String): ByteArray = ParcelFileDescriptor.AutoCloseInputStream(
        instrumentation.uiAutomation.executeShellCommand(command)).use { it.readBytes() }
    private fun await(seconds: Long = 30, test: () -> Boolean) {
        val deadline = System.currentTimeMillis()+seconds*1000
        while (System.currentTimeMillis()<deadline) { if (test()) return; Thread.sleep(200) }
        assertTrue("Timed out waiting for the requested state", test())
    }
    private fun screen(name: String) {
        compose.waitForIdle()
        instrumentation.waitForIdleSync()
        Thread.sleep(500)
        val bitmap=instrumentation.uiAutomation.takeScreenshot()
        File(out,name).outputStream().use { bitmap.compress(Bitmap.CompressFormat.PNG,100,it) };bitmap.recycle()
    }

    @Test fun optionalPackDownloadsRendersDeletesAndInstallsAgain() {
        val store=(context as GuideApplication).modelPacks
        val prefs=context.getSharedPreferences("model_packs",Context.MODE_PRIVATE)
        runBlocking {store.delete().join()};await { !store.state.value.installed && prefs.getLong("download_id",-1)<0 }
        val selected=mutableStateOf(false)
        lateinit var viewer: WebView
        lateinit var host: Activity
        compose.setContent {
            var c=LocalContext.current
            while (c is ContextWrapper && c !is Activity) c=c.baseContext
            host=c as Activity
            MaterialTheme {
                if (selected.value) OfflineModelDialog(modelId="pmn-classic-exterior",onViewerCreated={viewer=it},onDismiss={selected.value=false})
                else OfflineModelGallery {}
            }
        }
        compose.onNodeWithTag("model_pack_download").assertIsDisplayed()
        compose.onNodeWithTag("offline_3d_webview").assertDoesNotExist()
        screen("pack-not-installed.png")
        // Exercise real DownloadManager enqueue/cancel, including the persisted ID.
        store.setWifiOnly(false);store.download()
        await { prefs.getLong("download_id",-1)>=0 || store.state.value.phase==ModelPackPhase.Error }
        assertNotEquals(store.state.value.message,ModelPackPhase.Error,store.state.value.phase)
        runBlocking {store.cancel().join()};await { !store.state.value.busy && prefs.getLong("download_id",-1)<0 }
        assertFalse(store.pendingFile.exists())
        val realDownload=InstrumentationRegistry.getArguments().getString("realModelDownload","false")=="true"
        val master=File(context.getExternalFilesDir(null),"models3d/fixture.zip")
        var lastObservation=0L
        fun observeDownload() {
            if (System.currentTimeMillis()-lastObservation<5000) return
            lastObservation=System.currentTimeMillis()
            val item=JSONObject().put("phase",store.state.value.phase).put("observedBytes",store.state.value.downloaded)
            val id=prefs.getLong("download_id",-1)
            if (id>=0) context.getSystemService(android.app.DownloadManager::class.java)
                .query(android.app.DownloadManager.Query().setFilterById(id)).use {cursor->
                    if (cursor.moveToFirst()) for (column in listOf(android.app.DownloadManager.COLUMN_STATUS,
                        android.app.DownloadManager.COLUMN_REASON,android.app.DownloadManager.COLUMN_BYTES_DOWNLOADED_SO_FAR,
                        android.app.DownloadManager.COLUMN_TOTAL_SIZE_BYTES)) item.put(column,cursor.getLong(cursor.getColumnIndexOrThrow(column)))
                }
            File(out,"model-download-state.json").writeText(item.toString(2))
        }
        if (realDownload) {
            store.download()
            await { prefs.getLong("download_id",-1)>=0 }
            shell("input keyevent 3")
            Thread.sleep(5000)
            // With the gallery stopped, completion must be handled by the
            // production download receiver and verification job, without UI polling.
            await(900) { observeDownload();store.state.value.installed || store.state.value.phase==ModelPackPhase.Error }
            assertTrue(store.state.value.message,store.state.value.current)
            shell("am start -n ${host.componentName.flattenToString()} -f 0x00020000")
        } else {
            assertTrue("CI pack fixture missing",master.isFile)
            runBlocking { withContext(Dispatchers.IO) { master.copyTo(store.pendingFile,overwrite=true,bufferSize=1024*1024) };store.verifyAndActivate(store.pendingFile) }
        }
        compose.waitForIdle()
        assertTrue(store.state.value.current)
        assertEquals(store.descriptor.bytes,store.activeFile.length())
        assertFalse(store.pendingFile.exists())
        screen("pack-installed.png")
        compose.runOnIdle { selected.value=true }
        compose.waitForIdle()
        fun evaluate(script:String):String {
            val result=AtomicReference<String>();val done=CountDownLatch(1)
            instrumentation.runOnMainSync { viewer.evaluateJavascript(script) {result.set(it);done.countDown()} }
            check(done.await(10,TimeUnit.SECONDS));return result.get()
        }
        await(60) { evaluate("document.body && document.body.dataset.state")=="\"ready\"" }
        assertEquals("\"pmn-classic-exterior\"",evaluate("document.body.dataset.model"))
        assertTrue(evaluate("Number(document.querySelector('canvas').dataset.triangles)").toInt()>0)
        instrumentation.runOnMainSync { assertTrue(viewer.settings.blockNetworkLoads);assertFalse(viewer.settings.allowFileAccess) }
        Thread.sleep(1000);screen("model-initial.png")
        val xy=IntArray(2);var width=0;var height=0
        instrumentation.runOnMainSync {viewer.getLocationOnScreen(xy);width=viewer.width;height=viewer.height}
        shell("input swipe ${xy[0]+width/4} ${xy[1]+height/2} ${xy[0]+3*width/4} ${xy[1]+height/2} 650")
        Thread.sleep(1000);screen("model-rotated.png")
        assertFalse(File(out,"model-initial.png").readBytes().contentEquals(File(out,"model-rotated.png").readBytes()))
        // A corrupt replacement cannot disturb the current installed collection.
        store.pendingFile.writeBytes(byteArrayOf(1,2,3))
        assertThrows(IOException::class.java) { runBlocking {store.verifyAndActivate(store.pendingFile)} }
        assertTrue(store.state.value.current);store.pendingFile.delete()
        compose.onNodeWithContentDescription("Назад").performClick()
        compose.onNodeWithTag("model_pack_manage").performClick()
        compose.onNodeWithTag("model_pack_delete").performClick()
        val before=store.activeFile.parentFile!!.usableSpace
        compose.onNodeWithTag("model_pack_confirm_delete").performClick()
        await { !store.state.value.installed && !store.activeFile.exists() }
        val freed=store.activeFile.parentFile!!.usableSpace-before
        assertTrue("Deletion did not release the archive's occupied space: $freed",freed>store.descriptor.bytes*9/10)
        compose.onNodeWithTag("model_pack_download").assertIsDisplayed();screen("pack-deleted.png")
        // Repeat the real public download on API 36, or restore the same immutable
        // fixture on API 26. Both paths use the production validation/activation.
        if (realDownload) {
            store.download();await(900) {observeDownload();store.refresh();store.state.value.installed || store.state.value.phase==ModelPackPhase.Error}
            assertTrue(store.state.value.message,store.state.value.current)
        } else runBlocking { withContext(Dispatchers.IO) {master.copyTo(store.pendingFile,overwrite=true,bufferSize=1024*1024)};store.verifyAndActivate(store.pendingFile) }
        assertTrue(store.state.value.current)
        // All 615 approved GLBs must be readable through the new storage layer,
        // with each original SHA-256 checked by the production loader.
        var verifiedModels=0
        runBlocking(Dispatchers.IO) {
            for (name in store.descriptor.files.keys) {
                val raw=store.openModel(name)
                assertTrue(name,raw.size>12 && raw[0]=='g'.code.toByte() && raw[1]=='l'.code.toByte() &&
                    raw[2]=='T'.code.toByte() && raw[3]=='F'.code.toByte())
                verifiedModels++
            }
        }
        assertEquals(615,verifiedModels)
        File(out,"model-pack-result.json").writeText(JSONObject().put("passed",true).put("realDownload",realDownload)
            .put("bytesFreedByDelete",freed).put("modelCount",store.descriptor.files.size)
            .put("cancelVerified",true).put("corruptReplacementRejected",true).put("reinstalled",true)
            .put("allModelBytesVerified",verifiedModels).toString(2))
    }

    @Test fun notificationsAreDeduplicatedCanBeDisabledAndOpenUpdates() {
        UpdateNotifications.ensureChannel(context)
        assertTrue("CI must grant notification permission",UpdateNotifications.permitted(context))
        val p=context.getSharedPreferences("dlya_svoih",Context.MODE_PRIVATE)
        p.edit().remove("app_update_notified_code").remove("catalog_update_notified_version").commit()
        UpdateNotifications.configure(context,true)
        val scheduler=context.getSystemService(JobScheduler::class.java)
        assertNotNull(scheduler.getPendingJob(UpdateNotifications.JOB_ID))
        val app=RemoteApp(145,"0.3.140 · проверка",context.packageName,26,"https://example.com/update.apk",1,
            "a".repeat(64),"2f0a0908f269bc039311edb58fca8863347f1e4c3a7cfaddd909991cf1f0b509","Проверка уведомления")
        val manager=context.getSystemService(NotificationManager::class.java)
        manager.cancelAll();UpdateNotifications.appAvailable(context,app)
        await {manager.activeNotifications.any {it.id==UpdateNotifications.APP_ID}}
        val first=manager.activeNotifications.single {it.id==UpdateNotifications.APP_ID}
        Thread.sleep(100);UpdateNotifications.appAvailable(context,app)
        assertEquals(first.postTime,manager.activeNotifications.single {it.id==UpdateNotifications.APP_ID}.postTime)
        UpdateNotifications.catalogAvailable(context,RemoteCatalog(198,"https://example.com/catalog.zip",1,"b".repeat(64),"Проверка",138),197,144)
        await {manager.activeNotifications.any {it.id==UpdateNotifications.CATALOG_ID}}
        shell("cmd statusbar expand-notifications");Thread.sleep(500);screen("update-notifications.png");shell("cmd statusbar collapse")
        first.notification.contentIntent.send()
        // Reuse this instrumentation's UiAutomation connection. Starting the
        // separate `uiautomator` CLI while it owns that connection cannot dump UI.
        fun visibleText(node: android.view.accessibility.AccessibilityNodeInfo?): String {
            if (node==null) return ""
            val text=StringBuilder().append(node.text.orEmpty()).append('\n').append(node.contentDescription.orEmpty()).append('\n')
            for (index in 0 until node.childCount) {
                val child=node.getChild(index);text.append(visibleText(child));child?.recycle()
            }
            return text.toString()
        }
        try {
            await(45) {
                compose.waitForIdle()
                val root=instrumentation.uiAutomation.rootInActiveWindow
                val text=visibleText(root);root?.recycle()
                File(out,"notification-navigation-tree.txt").writeText(text)
                text.contains("Уведомления об обновлениях") && text.contains("Обновления")
            }
        } catch (e: Throwable) { screen("notification-navigation-failed.png");throw e }
        screen("notification-opened-updates.png")
        UpdateNotifications.configure(context,false)
        assertNull(scheduler.getPendingJob(UpdateNotifications.JOB_ID))
        await {manager.activeNotifications.none {it.id in setOf(UpdateNotifications.APP_ID,UpdateNotifications.CATALOG_ID)}}
        UpdateNotifications.appAvailable(context,app.copy(versionCode=146))
        assertTrue(manager.activeNotifications.none {it.id==UpdateNotifications.APP_ID})
        assertFalse(AppUpdateController.compatibleOffer(context,app.copy(packageName="wrong.package")))
        assertFalse(AppUpdateController.compatibleOffer(context,app.copy(signerSha256="0".repeat(64))))
        UpdateNotifications.configure(context,true)
        File(out,"notification-result.json").writeText(JSONObject().put("passed",true).put("sameVersionDeduplicated",true)
            .put("disableCancelsJobAndNotifications",true).put("tapOpensUpdates",true).put("invalidIdentityIgnored",true).toString(2))
        instrumentation.runOnMainSync {
            ActivityLifecycleMonitorRegistry.getInstance().getActivitiesInStage(Stage.RESUMED)
                .filterIsInstance<MainActivity>().forEach {it.finish()}
        }
    }
}
