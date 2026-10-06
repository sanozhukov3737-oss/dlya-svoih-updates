package ru.dlyasvoih.app

import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import ru.dlyasvoih.app.ui.theme.AtlasAppearance
import ru.dlyasvoih.app.ui.theme.DlyaSvoihTheme
import ru.dlyasvoih.app.ui.theme.LocalAtlasAppearance
import ru.dlyasvoih.app.ui.theme.THEME_SYSTEM

// A shortcut launch is one instance of "please go to this tab now": the token makes each firing
// distinct so picking the same launcher shortcut twice in a row (app already open, onNewIntent
// only) still navigates, even though the route string itself repeats.
data class ShortcutRequest(val route: String, val token: Long = System.nanoTime())

class MainActivity : ComponentActivity() {
    private val shortcutRequest = mutableStateOf<ShortcutRequest?>(null)

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
        enableEdgeToEdge()
        captureShortcut(intent)
        setContent {
            val preferences = remember { getSharedPreferences("appearance", MODE_PRIVATE) }
            var themeMode by remember { mutableIntStateOf(preferences.getInt("theme_mode", THEME_SYSTEM)) }
            var largeMode by remember { mutableStateOf(preferences.getBoolean("large_mode", false)) }
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
                    DlyaSvoihApp(shortcutRequest)
                }
            }
        }
    }

    companion object {
        const val EXTRA_SHORTCUT_ROUTE = "shortcut_route"
    }
}
