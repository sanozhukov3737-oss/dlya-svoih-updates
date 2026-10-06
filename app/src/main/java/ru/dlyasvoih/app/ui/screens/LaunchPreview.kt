package ru.dlyasvoih.app.ui.screens

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.size
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.ColorFilter
import androidx.compose.ui.res.colorResource
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.unit.dp
import ru.dlyasvoih.app.R

/** Matching fallback for Android 8–11; Android 12+ uses the system splash only. */
@Composable
fun LaunchPreview() {
    Box(Modifier.fillMaxSize().background(colorResource(R.color.launch_background)),
        contentAlignment = Alignment.Center) {
        Image(
            painter = painterResource(R.drawable.ic_launcher_foreground),
            contentDescription = "ДЛЯ СВОИХ",
            modifier = Modifier.size(224.dp),
            colorFilter = ColorFilter.tint(colorResource(R.color.launch_ink))
        )
    }
}
