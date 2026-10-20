package ru.dlyasvoih.app.ui.screens

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.asAndroidBitmap
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.test.captureToImage
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.unit.dp
import androidx.test.core.app.ApplicationProvider
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import java.io.File

class CatalogMenuIconTest {
    @get:Rule val compose = createComposeRule()
    private val context = ApplicationProvider.getApplicationContext<Context>()
    private val categories = linkedMapOf(
        "mines-antipersonnel" to "Противопехотные мины",
        "mines-antitank" to "Противотанковые мины",
        "submunitions" to "Суббоеприпасы",
        "mines-antivehicle" to "Противотранспортные мины",
        "mines-naval" to "Морские мины",
        "mines-antiland" to "Противодесантные мины",
        "mines-special" to "Специальные мины"
    )

    @Test fun everyRepresentativePhotoDecodesFromTheInstalledApplication() {
        for (key in categories.keys + "@engineering") {
            val resource = catalogMenuIconResource(key)
            assertNotEquals(key, catalogMenuIconResource(key, false), resource)
            val bitmap = BitmapFactory.decodeResource(context.resources, resource)
            assertNotNull("Missing menu photo: $key", bitmap)
            assertTrue(key, bitmap.width > 0 && bitmap.height > 0)
            bitmap.recycle()
        }
    }

    @Test fun menuPhotosRenderOfflineWithoutRetryButtons() {
        compose.setContent {
            MaterialTheme {
                Column(Modifier.testTag("menu_photos").padding(8.dp)) {
                    categories.forEach { (key, title) ->
                        Row { CatalogMenuIcon(key); Text(title, Modifier.padding(8.dp)) }
                    }
                }
            }
        }
        compose.onNodeWithText("Повторить").assertDoesNotExist()
        val bitmap = compose.onNodeWithTag("menu_photos").captureToImage().asAndroidBitmap()
        File(context.filesDir, "menu-icons.png").outputStream().use {
            assertTrue(bitmap.compress(Bitmap.CompressFormat.PNG, 100, it))
        }
    }
}
