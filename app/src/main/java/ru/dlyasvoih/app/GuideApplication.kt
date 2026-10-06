package ru.dlyasvoih.app

import android.app.Application
import android.app.ActivityManager
import android.content.Context
import coil3.ImageLoader
import coil3.SingletonImageLoader
import coil3.memory.MemoryCache
import ru.dlyasvoih.app.data.GuideRepository
import ru.dlyasvoih.app.data.local.GuideDatabase
import ru.dlyasvoih.app.data.update.ContentUpdater
import ru.dlyasvoih.app.data.update.RemoteCatalogSource
import ru.dlyasvoih.app.data.update.AppUpdateController

class GuideApplication : Application(), SingletonImageLoader.Factory {
    val repository by lazy {
        val db = GuideDatabase.create(this)
        @Suppress("DEPRECATION")
        val appCode = packageManager.getPackageInfo(packageName, 0).versionCode
        val prefs = getSharedPreferences("dlya_svoih", MODE_PRIVATE)
        GuideRepository(db, prefs, ContentUpdater(this, db), RemoteCatalogSource(cacheDir), appCode,
            AppUpdateController(this, prefs))
    }

    override fun newImageLoader(context: Context): ImageLoader {
        val manager = context.getSystemService(ActivityManager::class.java)
        val cacheMiB = (manager.memoryClass / 10).coerceIn(4, if (manager.isLowRamDevice) 12 else 32)
        return ImageLoader.Builder(context)
        .memoryCache { MemoryCache.Builder().maxSizeBytes(cacheMiB * 1024L * 1024L).build() }
        .diskCache(null)
        .build()
    }
}
