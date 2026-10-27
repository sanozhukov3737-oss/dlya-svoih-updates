package ru.dlyasvoih.app.data.models

import android.app.DownloadManager
import android.app.job.JobInfo
import android.app.job.JobParameters
import android.app.job.JobScheduler
import android.app.job.JobService
import android.content.BroadcastReceiver
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.system.Os
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import org.json.JSONObject
import ru.dlyasvoih.app.GuideApplication
import ru.dlyasvoih.app.data.update.RemoteFiles
import ru.dlyasvoih.app.data.update.UpdateNotifications
import java.io.File
import java.io.IOException
import java.util.concurrent.atomic.AtomicLong

data class ModelPackDescriptor(val version: Int, val url: String, val bytes: Long, val sha256: String,
    val files: Map<String, ModelPackArchive.Entry>) {
    companion object {
        fun load(context: Context): ModelPackDescriptor = context.assets.open("viewer3d/pack.json").bufferedReader().use {
            val json = JSONObject(it.readText())
            require(json.getInt("formatVersion") == 1)
            val files = json.getJSONObject("files")
            val entries = files.keys().asSequence().associateWith { name ->
                require(name.matches(Regex("[a-z0-9-]+\\.glb")))
                val value = files.getJSONObject(name)
                ModelPackArchive.Entry(value.getLong("bytes"), value.getString("sha256"))
            }
            val url = json.getString("url").also { value -> RemoteFiles.httpsUrl(value) }
            val bytes = json.getLong("bytes").also { size -> require(size in 1..(2L * 1024 * 1024 * 1024)) }
            val sha = json.getString("sha256").also { value -> require(value.matches(Regex("[a-f0-9]{64}"))) }
            require(entries.size == json.getInt("modelCount") && entries.isNotEmpty())
            ModelPackDescriptor(json.getInt("version"), url, bytes, sha, entries)
        }
    }
}

enum class ModelPackPhase { Idle, Downloading, Waiting, Verifying, Error }
data class ModelPackState(val installed: Boolean = false, val current: Boolean = false, val installedBytes: Long = 0,
    val phase: ModelPackPhase = ModelPackPhase.Idle, val downloaded: Long = 0, val message: String = "") {
    val busy get() = phase in setOf(ModelPackPhase.Downloading, ModelPackPhase.Waiting, ModelPackPhase.Verifying)
}

class ModelPackStore(private val context: Context) {
    val descriptor by lazy { ModelPackDescriptor.load(context) }
    private val prefs = context.getSharedPreferences("model_packs", Context.MODE_PRIVATE)
    private val downloads = context.getSystemService(DownloadManager::class.java)
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val lock = Mutex()
    private val generation = AtomicLong()
    private var refreshing: Job? = null
    private val directory: File get() = File(requireNotNull(context.getExternalFilesDir(null)) {
        "Хранилище недоступно. Проверьте свободное место." }, "models3d").apply { check(isDirectory || mkdirs()) }
    internal val activeFile get() = File(directory, "collection.zip")
    internal val pendingFile get() = File(directory, "download.part.zip")
    private val mutableState = MutableStateFlow(installedState())
    val state = mutableState.asStateFlow()
    val wifiOnly get() = prefs.getBoolean("wifi_only", true)
    fun setWifiOnly(value: Boolean) { prefs.edit().putBoolean("wifi_only", value).apply() }

    private fun installedState(phase: ModelPackPhase = ModelPackPhase.Idle, downloaded: Long = 0, message: String = ""): ModelPackState {
        val size = runCatching { activeFile.takeIf { it.isFile }?.length() ?: 0L }.getOrDefault(0L)
        return ModelPackState(size > 0, size > 0 && size == descriptor.bytes && prefs.getString("active_sha", null) == descriptor.sha256,
            size, phase, downloaded, message)
    }
    fun refresh() {
        if (refreshing?.isActive == true) return
        refreshing = scope.launch { refreshNow() }
    }
    private suspend fun refreshNow() {
        val id = prefs.getLong("download_id", -1)
        if (id < 0) {
            if (mutableState.value.phase != ModelPackPhase.Verifying)
                mutableState.value = installedState(message = prefs.getString("error", "").orEmpty(),
                    phase = if (prefs.contains("error")) ModelPackPhase.Error else ModelPackPhase.Idle)
            return
        }
        downloads.query(DownloadManager.Query().setFilterById(id)).use { cursor ->
            if (!cursor.moveToFirst()) {
                fail("Загрузка прервана. Модели можно скачать снова."); return
            }
            val bytes = cursor.getLong(cursor.getColumnIndexOrThrow(DownloadManager.COLUMN_BYTES_DOWNLOADED_SO_FAR))
            when (cursor.getInt(cursor.getColumnIndexOrThrow(DownloadManager.COLUMN_STATUS))) {
                DownloadManager.STATUS_SUCCESSFUL -> finishPendingDownload()
                DownloadManager.STATUS_FAILED -> fail("Не удалось скачать модели. Проверьте интернет и свободное место.")
                DownloadManager.STATUS_PAUSED, DownloadManager.STATUS_PENDING -> mutableState.value = installedState(ModelPackPhase.Waiting, bytes)
                else -> mutableState.value = installedState(ModelPackPhase.Downloading, bytes)
            }
        }
    }
    fun download() {
        if (mutableState.value.busy) return
        val token = generation.incrementAndGet()
        mutableState.value = installedState(ModelPackPhase.Downloading)
        scope.launch {
            lock.withLock {
                try {
                    require(directory.usableSpace > descriptor.bytes + 32L * 1024 * 1024) { "Недостаточно свободного места для пакета моделей." }
                    pendingFile.delete()
                    val request = DownloadManager.Request(Uri.parse(descriptor.url))
                        .setTitle("ДЛЯ СВОИХ — 3D-модели")
                        .setDescription("Коллекция из ${descriptor.files.size} моделей")
                        .setMimeType("application/zip")
                        .setAllowedOverMetered(!wifiOnly).setAllowedOverRoaming(false)
                        .setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE)
                        .setDestinationInExternalFilesDir(context, "models3d", pendingFile.name)
                    if (generation.get() != token) return@withLock
                    val id = downloads.enqueue(request)
                    prefs.edit().putLong("download_id", id).putString("download_sha", descriptor.sha256).remove("error").commit()
                } catch (e: Exception) { fail(e.message ?: "Не удалось начать скачивание моделей.") }
            }
            if (generation.get() == token) refreshNow()
        }
    }
    fun cancel() {
        generation.incrementAndGet()
        context.getSystemService(JobScheduler::class.java).cancel(VERIFY_JOB_ID)
        scope.launch { lock.withLock {
            clearDownload(); mutableState.value = installedState()
        } }
    }
    fun delete() {
        generation.incrementAndGet()
        context.getSystemService(JobScheduler::class.java).cancel(VERIFY_JOB_ID)
        scope.launch { lock.withLock {
            try {
                clearDownload()
                check(!activeFile.exists() || activeFile.delete()) { "Не удалось удалить модели. Повторите попытку." }
                prefs.edit().remove("active_sha").remove("active_version").apply()
                mutableState.value = installedState()
            } catch (e: Exception) { mutableState.value = installedState(ModelPackPhase.Error, message = e.message.orEmpty()) }
        } }
    }
    private fun clearDownload() {
        val id = prefs.getLong("download_id", -1)
        if (id >= 0) downloads.remove(id)
        pendingFile.delete()
        prefs.edit().remove("download_id").remove("download_sha").remove("error").commit()
    }
    private fun fail(message: String) {
        clearDownload()
        prefs.edit().putString("error", message).apply()
        mutableState.value = installedState(ModelPackPhase.Error, message = message)
    }
    suspend fun finishPendingDownload() = lock.withLock {
        val id = prefs.getLong("download_id", -1)
        if (id < 0) return@withLock
        val complete = downloads.query(DownloadManager.Query().setFilterById(id)).use { cursor ->
            cursor.moveToFirst() && cursor.getInt(cursor.getColumnIndexOrThrow(DownloadManager.COLUMN_STATUS)) == DownloadManager.STATUS_SUCCESSFUL
        }
        if (!complete) return@withLock
        val token = generation.get()
        mutableState.value = installedState(ModelPackPhase.Verifying, descriptor.bytes)
        try {
            require(prefs.getString("download_sha", null) == descriptor.sha256) { "Коллекция обновилась. Повторите скачивание моделей." }
            verifyAndActivate(pendingFile, token)
            downloads.remove(id)
            prefs.edit().remove("download_id").remove("download_sha").remove("error").commit()
            mutableState.value = installedState()
            UpdateNotifications.modelsReady(context)
        } catch (e: CancellationException) { throw e }
        catch (e: Exception) {
            if (generation.get() == token) fail(e.message ?: "Не удалось проверить пакет моделей.")
        }
    }
    internal suspend fun verifyAndActivate(candidate: File, token: Long = generation.get()) {
        runInterruptible(Dispatchers.IO) {
            ModelPackArchive.verify(candidate, descriptor.bytes, descriptor.sha256, descriptor.files) { generation.get() != token }
        }
        currentCoroutineContext().ensureActive()
        check(generation.get() == token) { "Установка отменена" }
        Os.rename(candidate.absolutePath, activeFile.absolutePath)
        prefs.edit().putString("active_sha", descriptor.sha256).putInt("active_version", descriptor.version).commit()
        mutableState.value = installedState()
    }
    fun openModel(name: String): ByteArray {
        val entry = descriptor.files[name] ?: throw IOException("Неизвестная модель")
        return ModelPackArchive.read(activeFile, name, entry)
    }
    companion object {
        const val VERIFY_JOB_ID = 13902
        fun scheduleVerification(context: Context) {
            context.getSystemService(JobScheduler::class.java).schedule(JobInfo.Builder(VERIFY_JOB_ID,
                ComponentName(context, ModelPackVerifyJob::class.java)).setMinimumLatency(0).setPersisted(true).build())
        }
    }
}

class ModelPackDownloadReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != DownloadManager.ACTION_DOWNLOAD_COMPLETE) return
        val prefs = context.getSharedPreferences("model_packs", Context.MODE_PRIVATE)
        val id = intent.getLongExtra(DownloadManager.EXTRA_DOWNLOAD_ID, -1)
        if (id >= 0 && id == prefs.getLong("download_id", -1)) ModelPackStore.scheduleVerification(context)
    }
}

class ModelPackVerifyJob : JobService() {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private var task: Job? = null
    override fun onStartJob(params: JobParameters): Boolean {
        task = scope.launch {
            try { (application as GuideApplication).modelPacks.finishPendingDownload() }
            finally { if (isActive) jobFinished(params, false) }
        }
        return true
    }
    override fun onStopJob(params: JobParameters): Boolean { task?.cancel(); return true }
    override fun onDestroy() { scope.cancel(); super.onDestroy() }
}
