package ru.dlyasvoih.app

import android.content.Intent
import android.os.Bundle
import android.os.Build
import android.os.SystemClock
import android.view.View
import android.view.ViewTreeObserver
import androidx.activity.SystemBarStyle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.SideEffect
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import ru.dlyasvoih.app.ui.theme.AtlasAppearance
import ru.dlyasvoih.app.ui.theme.DlyaSvoihTheme
import ru.dlyasvoih.app.ui.theme.LocalAtlasAppearance
import ru.dlyasvoih.app.ui.theme.THEME_SYSTEM
import ru.dlyasvoih.app.ui.theme.THEME_LIGHT
import ru.dlyasvoih.app.ui.theme.THEME_DARK
import androidx.core.view.WindowCompat

// A shortcut launch is one instance of "please go to this tab now": the token makes each firing
// distinct so picking the same launcher shortcut twice in a row (app already open, onNewIntent
// only) still navigates, even though the route string itself repeats.
data class ShortcutRequest(val route: String, val token: Long = System.nanoTime())

class MainActivity : ComponentActivity() {
    private val shortcutRequest = mutableStateOf<ShortcutRequest?>(null)
    private var firstFrameReady = false
    private var launchVisible by mutableStateOf(true)

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        captureShortcut(intent)
    }

    private fun captureShortcut(intent: Intent?) {
        val route = intent?.getStringExtra(EXTRA_SHORTCUT_ROUTE) ?: return
        shortcutRequest.value = ShortcutRequest(route)
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val nativeSplash = Build.VERSION.SDK_INT >= 31
        val firstLaunch = savedInstanceState == null
        launchVisible = firstLaunch
        val launchDeadline = SystemClock.elapsedRealtime() + if (firstLaunch) 700L else 0L
        enableEdgeToEdge(
            statusBarStyle = SystemBarStyle.light(android.graphics.Color.TRANSPARENT, android.graphics.Color.TRANSPARENT),
            navigationBarStyle = SystemBarStyle.light(android.graphics.Color.TRANSPARENT, 0xFF171C18.toInt())
        )
        if (nativeSplash && firstLaunch) {
            splashScreen.setOnExitAnimationListener { splash ->
                splash.animate().alpha(0f).setDuration(180L).withEndAction {
                    splash.remove()
                    launchVisible = false
                }.start()
            }
        }
        captureShortcut(intent)
        setContent {
            val preferences = remember { getSharedPreferences("appearance", MODE_PRIVATE) }
            var themeMode by remember { mutableIntStateOf(preferences.getInt("theme_mode", THEME_SYSTEM)) }
            var largeMode by remember { mutableStateOf(preferences.getBoolean("large_mode", false)) }
            val dark = when (themeMode) {
                THEME_LIGHT -> false
                THEME_DARK -> true
                else -> isSystemInDarkTheme()
            }
            SideEffect {
                val lightBars = launchVisible || !dark
                WindowCompat.getInsetsController(window, window.decorView).apply {
                    isAppearanceLightStatusBars = lightBars
                    isAppearanceLightNavigationBars = lightBars
                }
            }
            DlyaSvoihTheme(themeMode, largeMode) {
                CompositionLocalProvider(LocalAtlasAppearance provides AtlasAppearance(
                    themeMode = themeMode,
                    largeMode = largeMode,
                    setThemeMode = { value ->
                        themeMode = value
                        preferences.edit().putInt("theme_mode", value).apply()
                    },
                    setLargeMode = { value ->
                        largeMode = value
                        preferences.edit().putBoolean("large_mode", value).apply()
                    }
                )) {
                    DlyaSvoihApp(shortcutRequest, nativeSplash = nativeSplash, onLaunchReady = {
                        firstFrameReady = true
                        if (!nativeSplash) launchVisible = false
                    })
                }
            }
        }
        if (nativeSplash && firstLaunch) {
            // Compose initializes the database underneath the system splash.
            // Errors also release it so the retry screen stays usable.
            val content = findViewById<View>(android.R.id.content)
            content.viewTreeObserver.addOnPreDrawListener(object : ViewTreeObserver.OnPreDrawListener {
                override fun onPreDraw(): Boolean {
                    if (!firstFrameReady || SystemClock.elapsedRealtime() < launchDeadline) return false
                    content.viewTreeObserver.removeOnPreDrawListener(this)
                    return true
                }
            })
        }
    }

    companion object {
        const val EXTRA_SHORTCUT_ROUTE = "shortcut_route"
    }
}
