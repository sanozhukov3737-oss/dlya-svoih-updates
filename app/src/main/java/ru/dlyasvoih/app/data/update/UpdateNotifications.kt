package ru.dlyasvoih.app.data.update

import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.job.JobInfo
import android.app.job.JobParameters
import android.app.job.JobScheduler
import android.app.job.JobService
import android.content.BroadcastReceiver
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.app.NotificationCompat
import kotlinx.coroutines.*
import ru.dlyasvoih.app.GuideApplication
import ru.dlyasvoih.app.MainActivity
import ru.dlyasvoih.app.R

object UpdateNotifications {
    const val JOB_ID = 13901
    const val CHANNEL = "updates"
    const val APP_ID = 13911
    const val CATALOG_ID = 13912
    const val MODELS_ID = 13913
    private const val PERIOD = 6L * 60 * 60 * 1000
    private fun prefs(context: Context) = context.getSharedPreferences("dlya_svoih", Context.MODE_PRIVATE)
    fun wanted(context: Context) = prefs(context).getBoolean("update_notifications_enabled", true)
    fun permitted(context: Context): Boolean {
        val manager = context.getSystemService(NotificationManager::class.java)
        return (Build.VERSION.SDK_INT < 33 || context.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED) &&
            manager.areNotificationsEnabled() && manager.getNotificationChannel(CHANNEL)?.importance != NotificationManager.IMPORTANCE_NONE
    }
    fun enabled(context: Context) = wanted(context) && permitted(context)
    fun ensureChannel(context: Context) {
        context.getSystemService(NotificationManager::class.java).createNotificationChannel(
            NotificationChannel(CHANNEL, "Обновления", NotificationManager.IMPORTANCE_DEFAULT).apply {
                description = "Новые версии приложения и каталога, готовность скачанных моделей"
            })
    }
    fun configure(context: Context, value: Boolean) {
        prefs(context).edit().putBoolean("update_notifications_enabled", value).apply()
        schedule(context)
        if (!value) context.getSystemService(NotificationManager::class.java).apply {
            cancel(APP_ID); cancel(CATALOG_ID); cancel(MODELS_ID)
        }
    }
    fun schedule(context: Context) {
        ensureChannel(context)
        val scheduler = context.getSystemService(JobScheduler::class.java)
        if (!enabled(context)) { scheduler.cancel(JOB_ID); return }
        if (scheduler.getPendingJob(JOB_ID) == null) scheduler.schedule(JobInfo.Builder(JOB_ID,
            ComponentName(context, UpdateNotificationJob::class.java))
            .setRequiredNetworkType(JobInfo.NETWORK_TYPE_ANY).setPeriodic(PERIOD, 60L*60*1000)
            .setPersisted(true).build())
    }
    private fun notification(context: Context, id: Int, title: String, text: String, route: String): Boolean {
        if (!enabled(context)) return false
        val intent = Intent(context, MainActivity::class.java)
            .putExtra(MainActivity.EXTRA_SHORTCUT_ROUTE, route)
            .addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP)
        val pending = PendingIntent.getActivity(context, id, intent, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        val item = NotificationCompat.Builder(context, CHANNEL).setSmallIcon(R.drawable.icon_notification)
            .setContentTitle(title).setContentText(text).setStyle(NotificationCompat.BigTextStyle().bigText(text))
            .setContentIntent(pending).setAutoCancel(true).setOnlyAlertOnce(true).build()
        return runCatching { context.getSystemService(NotificationManager::class.java).notify(id, item); true }.getOrDefault(false)
    }
    @Synchronized fun appAvailable(context: Context, app: RemoteApp) {
        val p = prefs(context)
        if (p.getInt("app_update_notified_code", 0) >= app.versionCode || !AppUpdateController.compatibleOffer(context, app)) return
        if (notification(context, APP_ID, "Доступно обновление ${app.versionName}",
            "Новая версия «ДЛЯ СВОИХ». Нажмите, чтобы посмотреть изменения и установить.", "catalog/updates"))
            p.edit().putInt("app_update_notified_code", app.versionCode).apply()
    }
    @Synchronized fun catalogAvailable(context: Context, offer: RemoteCatalog, installed: Long, appCode: Long) {
        val p = prefs(context)
        if (offer.version <= installed || offer.minAppCode > appCode || p.getLong("catalog_update_notified_version", 0) >= offer.version) return
        if (notification(context, CATALOG_ID, "Доступен каталог ${offer.version}",
            "Новые материалы для справочника. Нажмите, чтобы посмотреть обновление.", "catalog/updates"))
            p.edit().putLong("catalog_update_notified_version", offer.version).apply()
    }
    fun modelsReady(context: Context) {
        notification(context, MODELS_ID, "3D-модели готовы", "Коллекция скачана и проверена. Можно смотреть без интернета.", "catalog/models")
    }
    suspend fun check(context: Context) {
        if (!enabled(context)) return
        val p = prefs(context)
        val files = RemoteFiles()
        val text = withContext(Dispatchers.IO) { files.text(RemoteAppSource.FEED_URL) }
        val app = RemoteAppSource.decode(text)
        if (app != null && AppUpdateController.compatibleOffer(context, app)) {
            p.edit().putString("app_update_cached_offer", RemoteAppSource.encode(app)).apply()
            appAvailable(context, app)
        } else context.getSystemService(NotificationManager::class.java).cancel(APP_ID)
        val address = p.getString("update_source", RemoteAppSource.FEED_URL).orEmpty()
        if (address.isNotBlank()) {
            val catalog = RemoteCatalogSource.decode(if (address == RemoteAppSource.FEED_URL) text else
                withContext(Dispatchers.IO) { files.text(address) })
            val installed = (context.applicationContext as GuideApplication).repository.contentVersion()
            @Suppress("DEPRECATION")
            val code = context.packageManager.getPackageInfo(context.packageName, 0).let {
                if (Build.VERSION.SDK_INT >= 28) it.longVersionCode else it.versionCode.toLong()
            }
            catalogAvailable(context, catalog, installed, code)
            if (catalog.version <= installed) context.getSystemService(NotificationManager::class.java).cancel(CATALOG_ID)
        }
    }
}

class UpdateNotificationJob : JobService() {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private var task: Job? = null
    override fun onStartJob(params: JobParameters): Boolean {
        task = scope.launch {
            try { UpdateNotifications.check(this@UpdateNotificationJob) }
            catch (e: CancellationException) { throw e }
            catch (_: Exception) { /* Periodic checks retry later; manual checks remain available. */ }
            finally { if (isActive) jobFinished(params, false) }
        }
        return true
    }
    override fun onStopJob(params: JobParameters): Boolean { task?.cancel(); return true }
    override fun onDestroy() { scope.cancel(); super.onDestroy() }
}

class UpdateScheduleReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action in setOf(Intent.ACTION_BOOT_COMPLETED, Intent.ACTION_MY_PACKAGE_REPLACED)) {
            UpdateNotifications.schedule(context)
            if (context.getSharedPreferences("model_packs", Context.MODE_PRIVATE).getLong("download_id", -1) >= 0)
                ru.dlyasvoih.app.data.models.ModelPackStore.scheduleVerification(context)
        }
    }
}
