package ru.dlyasvoih.app.ui.screens

import androidx.compose.material3.MaterialTheme
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import ru.dlyasvoih.app.data.local.CardEntity

class ComparisonSheetTest {
    @get:Rule val compose = createComposeRule()

    private fun card(id: String, body: String) = CardEntity(
        rowId = 1, id = id, section = "S1", categoryId = "C1", title = id,
        summary = "Описание $id", body = "| Параметр | Значение |\n| --- | --- |\n$body",
        tags = "", sortTitle = id, searchText = "", thumbnailPath = null,
        contentStatus = "reviewed", reviewedAt = null)

    @Test fun reversedFieldOrderAlignsAndSelectionRecomputesRows() {
        val a = card("A", "| Цвет | Красный |\n| Высота | 10 см |")
        val b = card("B", "| Высота | 20 см |\n| Цвет | Синий |")
        val c = card("C", "| Ширина | 5 см |")
        compose.setContent { MaterialTheme { ComparisonSheet(a, listOf(b, c), {}) } }
        compose.onNodeWithTag("comparison_0_left").assertTextEquals("Красный")
        compose.onNodeWithTag("comparison_0_right").assertTextEquals("Синий")
        val left = compose.onNodeWithTag("comparison_0_left").fetchSemanticsNode().boundsInRoot
        val right = compose.onNodeWithTag("comparison_0_right").fetchSemanticsNode().boundsInRoot
        assertEquals(left.top, right.top, 0.5f)
        compose.onNodeWithText("C").performClick()
        compose.onNodeWithTag("comparison_0_right").assertTextEquals("Нет данных в карточке")
        compose.onNodeWithTag("comparison_table").performScrollToNode(hasTestTag("comparison_2_right"))
        compose.onNodeWithTag("comparison_2_right").assertTextEquals("5 см")
    }

    @Test fun allFieldsRemainReachableInALongComparison() {
        val rows = (1..40).joinToString("\n") { "| Поле $it | Значение $it |" }
        compose.setContent { MaterialTheme { ComparisonSheet(card("A", rows), listOf(card("B", rows)), {}) } }
        compose.onNodeWithTag("comparison_table").performScrollToNode(hasTestTag("comparison_39_left"))
        compose.onNodeWithTag("comparison_39_left").assertTextEquals("Значение 40").assertIsDisplayed()
        compose.onNodeWithTag("comparison_39_right").assertTextEquals("Значение 40").assertIsDisplayed()
    }
}
