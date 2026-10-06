package ru.dlyasvoih.app.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Shapes
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

const val THEME_SYSTEM = 0
const val THEME_LIGHT = 1
const val THEME_DARK = 2

@Immutable
data class AtlasAppearance(
    val themeMode: Int = THEME_SYSTEM,
    val largeMode: Boolean = false,
    val setThemeMode: (Int) -> Unit = {},
    val setLargeMode: (Boolean) -> Unit = {}
)

val LocalAtlasAppearance = staticCompositionLocalOf { AtlasAppearance() }

private val AtlasGreen = Color(0xFFAFC58F)
private val AtlasSand = Color(0xFFD5B477)
private val AtlasAmber = Color(0xFFE1A34A)

private val DarkColors = darkColorScheme(
    primary = AtlasGreen,
    onPrimary = Color(0xFF17210F),
    primaryContainer = Color(0xFF334328),
    onPrimaryContainer = Color(0xFFD6EABC),
    secondary = AtlasSand,
    onSecondary = Color(0xFF2A2114),
    secondaryContainer = Color(0xFF493B25),
    onSecondaryContainer = Color(0xFFF5DDAE),
    tertiary = AtlasAmber,
    onTertiary = Color(0xFF2D2008),
    tertiaryContainer = Color(0xFF543B0F),
    onTertiaryContainer = Color(0xFFFFDE9D),
    error = Color(0xFFFFB4AB),
    errorContainer = Color(0xFF72342F),
    background = Color(0xFF101411),
    surface = Color(0xFF171C18),
    surfaceVariant = Color(0xFF252C26),
    surfaceContainer = Color(0xFF1D231E),
    surfaceContainerHigh = Color(0xFF272E28),
    outline = Color(0xFF778075),
    outlineVariant = Color(0xFF3E463E),
    onBackground = Color(0xFFF0F2EA),
    onSurface = Color(0xFFF0F2EA),
    onSurfaceVariant = Color(0xFFC2C9BE)
)

private val LightColors = lightColorScheme(
    primary = Color(0xFF455E34),
    onPrimary = Color.White,
    primaryContainer = Color(0xFFD9EBC7),
    onPrimaryContainer = Color(0xFF18250F),
    secondary = Color(0xFF705A37),
    onSecondary = Color.White,
    secondaryContainer = Color(0xFFF4DFB8),
    onSecondaryContainer = Color(0xFF281D0B),
    tertiary = Color(0xFF805600),
    onTertiary = Color.White,
    tertiaryContainer = Color(0xFFFFDDA1),
    onTertiaryContainer = Color(0xFF291800),
    error = Color(0xFFBA1A1A),
    errorContainer = Color(0xFFFFDAD6),
    background = Color(0xFFF2F1E9),
    surface = Color(0xFFFAFAF3),
    surfaceVariant = Color(0xFFE3E7DC),
    surfaceContainer = Color(0xFFECEDE5),
    surfaceContainerHigh = Color(0xFFE5E7DE),
    outline = Color(0xFF74796F),
    outlineVariant = Color(0xFFC4C9BD),
    onBackground = Color(0xFF1A1C18),
    onSurface = Color(0xFF1A1C18),
    onSurfaceVariant = Color(0xFF44483F)
)

private fun atlasTypography(scale: Float) = Typography(
    displaySmall = TextStyle(fontSize = (34 * scale).sp, lineHeight = (38 * scale).sp, fontWeight = FontWeight.Black),
    headlineLarge = TextStyle(fontSize = (30 * scale).sp, lineHeight = (35 * scale).sp, fontWeight = FontWeight.Black),
    headlineMedium = TextStyle(fontSize = (25 * scale).sp, lineHeight = (30 * scale).sp, fontWeight = FontWeight.ExtraBold),
    headlineSmall = TextStyle(fontSize = (22 * scale).sp, lineHeight = (27 * scale).sp, fontWeight = FontWeight.ExtraBold),
    titleLarge = TextStyle(fontSize = (20 * scale).sp, lineHeight = (25 * scale).sp, fontWeight = FontWeight.Bold),
    titleMedium = TextStyle(fontSize = (16 * scale).sp, lineHeight = (21 * scale).sp, fontWeight = FontWeight.Bold),
    titleSmall = TextStyle(fontSize = (14 * scale).sp, lineHeight = (19 * scale).sp, fontWeight = FontWeight.Bold),
    bodyLarge = TextStyle(fontSize = (17 * scale).sp, lineHeight = (25 * scale).sp),
    bodyMedium = TextStyle(fontSize = (14 * scale).sp, lineHeight = (20 * scale).sp),
    bodySmall = TextStyle(fontSize = (12 * scale).sp, lineHeight = (17 * scale).sp),
    labelLarge = TextStyle(fontSize = (13 * scale).sp, lineHeight = (17 * scale).sp, fontWeight = FontWeight.Bold, letterSpacing = 0.4.sp),
    labelMedium = TextStyle(fontSize = (11 * scale).sp, lineHeight = (15 * scale).sp, fontWeight = FontWeight.Bold, letterSpacing = 0.45.sp),
    labelSmall = TextStyle(fontSize = (10 * scale).sp, lineHeight = (13 * scale).sp, fontWeight = FontWeight.Bold, letterSpacing = 0.35.sp)
)

private val AtlasShapes = Shapes(
    extraSmall = RoundedCornerShape(6.dp),
    small = RoundedCornerShape(10.dp),
    medium = RoundedCornerShape(16.dp),
    large = RoundedCornerShape(22.dp),
    extraLarge = RoundedCornerShape(28.dp)
)

@Composable
fun DlyaSvoihTheme(
    themeMode: Int = THEME_SYSTEM,
    largeMode: Boolean = false,
    content: @Composable () -> Unit
) {
    val dark = when (themeMode) {
        THEME_LIGHT -> false
        THEME_DARK -> true
        else -> isSystemInDarkTheme()
    }
    MaterialTheme(
        colorScheme = if (dark) DarkColors else LightColors,
        typography = atlasTypography(if (largeMode) 1.14f else 1f),
        shapes = AtlasShapes,
        content = content
    )
}
