package ru.dlyasvoih.app.ui.screens

import androidx.compose.material3.MaterialTheme
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import ru.dlyasvoih.app.data.local.CardEntity
import ru.dlyasvoih.app.data.local.CardPreview

class ComparisonSheetTest {
    @get:Rule val compose = createComposeRule()

    private fun card(id: String, body: String) = CardEntity(
        rowId = 1, id = id, section = "S1", categoryId = "C1", title = id,
        summary = "Описание $id", body = "| Параметр | Значение |\n| --- | --- |\n$body",
        tags = "", sortTitle = id, searchText = "", thumbnailPath = null,
        contentStatus = "reviewed", reviewedAt = null)

    private fun preview(card: CardEntity) = CardPreview(card.id, card.section, card.title,
        card.summary, card.thumbnailPath, card.categoryId, card.contentStatus, card.modelStatus)

    private fun show(a: CardEntity, others: List<CardEntity>) {
        compose.setContent { MaterialTheme {
            ComparisonSheet(a, others.map(::preview), { id -> others.firstOrNull { it.id == id } }, {})
        } }
        compose.waitUntil(10_000) { compose.onAllNodesWithTag("comparison_table").fetchSemanticsNodes().isNotEmpty() }
        compose.onNodeWithTag("comparison_table").performScrollToNode(hasTestTag("comparison_0_left"))
    }

    @Test fun reversedFieldOrderAlignsAndSelectionRecomputesRows() {
        val a = card("A", "| Цвет | Красный |\n| Высота | 10 см |")
        val b = card("B", "| Высота | 20 см |\n| Цвет | Синий |")
        val c = card("C", "| Ширина | 5 см |")
        show(a, listOf(b, c))
        compose.onNodeWithTag("comparison_0_left").assertTextEquals("Красный")
        compose.onNodeWithTag("comparison_0_right").assertTextEquals("Синий")
        val left = compose.onNodeWithTag("comparison_0_left").fetchSemanticsNode().boundsInRoot
        val right = compose.onNodeWithTag("comparison_0_right").fetchSemanticsNode().boundsInRoot
        assertEquals(left.top, right.top, 0.5f)
        compose.onNodeWithTag("comparison_choose").performClick()
        compose.onNodeWithTag("comparison_option_B").performClick()
        compose.onNodeWithTag("comparison_option_C").performClick()
        compose.onNodeWithTag("comparison_apply").performClick()
        compose.waitUntil(10_000) { compose.onAllNodesWithText("Нет данных в карточке").fetchSemanticsNodes().isNotEmpty() }
        compose.onNodeWithTag("comparison_0_right").assertTextEquals("Нет данных в карточке")
        compose.onNodeWithTag("comparison_table").performScrollToNode(hasTestTag("comparison_2_right"))
        compose.onNodeWithTag("comparison_2_right").assertTextEquals("5 см")
    }

    @Test fun allFieldsRemainReachableInALongComparison() {
        val rows = (1..40).joinToString("\n") { "| Поле $it | Значение $it |" }
        show(card("A", rows), listOf(card("B", rows)))
        val top = compose.onNodeWithTag("comparison_header_0").fetchSemanticsNode().boundsInRoot.top
        compose.onNodeWithTag("comparison_table").performScrollToNode(hasTestTag("comparison_39_left"))
        compose.onNodeWithTag("comparison_39_left").assertTextEquals("Значение 40").assertIsDisplayed()
        compose.onNodeWithTag("comparison_39_right").assertTextEquals("Значение 40").assertIsDisplayed()
        compose.onNodeWithTag("comparison_header_0").assertIsDisplayed()
        assertEquals(top, compose.onNodeWithTag("comparison_header_0").fetchSemanticsNode().boundsInRoot.top, 0.5f)
    }

    @Test fun threeColumnsAlignAndAThirdCandidateCannotBeAdded() {
        val a = card("A", "| Цвет | Красный |")
        val b = card("B", "| Цвет | Синий |")
        val c = card("C", "| Цвет | Зелёный |")
        val d = card("D", "| Цвет | Белый |")
        show(a, listOf(b,c,d))
        compose.onNodeWithTag("comparison_choose").performClick()
        compose.onNodeWithTag("comparison_option_C").performClick()
        compose.onNodeWithTag("comparison_option_D").assertIsNotEnabled()
        compose.onNodeWithTag("comparison_apply").performClick()
        compose.waitUntil(10_000) { compose.onAllNodesWithTag("comparison_0_third").fetchSemanticsNodes().isNotEmpty() }
        compose.onNodeWithTag("comparison_0_left").assertTextEquals("Красный")
        compose.onNodeWithTag("comparison_0_right").assertTextEquals("Синий")
        compose.onNodeWithTag("comparison_0_third").assertTextEquals("Зелёный")
        val left = compose.onNodeWithTag("comparison_0_left").fetchSemanticsNode().boundsInRoot
        val right = compose.onNodeWithTag("comparison_0_right").fetchSemanticsNode().boundsInRoot
        assertEquals(left.top, right.top, 0.5f)
        compose.onNodeWithTag("comparison_columns").performTouchInput { swipeLeft() }
        compose.onNodeWithTag("comparison_header_2").assertIsDisplayed()
        compose.onNodeWithTag("comparison_0_third").assertIsDisplayed()
        compose.onNodeWithTag("comparison_remove_2").performClick()
        compose.waitUntil(10_000) { compose.onAllNodesWithTag("comparison_header_2").fetchSemanticsNodes().isEmpty() }
    }

    @Test fun searchReachesTheWholeCategoryAndFiltersMismatchedPreviews() {
        val a = card("A", "| Цвет | Красный |")
        val options = (1..26).map { card("Z$it", "| Цвет | Синий |") }
        val wrong = card("Wrong", "| Цвет | Белый |").copy(categoryId = "Other")
        show(a, options + wrong)
        compose.onNodeWithTag("comparison_choose").performClick()
        compose.onNodeWithTag("comparison_search").performTextInput("wrong")
        compose.onNodeWithText("Карточки не найдены").assertIsDisplayed()
        compose.onNodeWithTag("comparison_search").performTextReplacement("z26")
        compose.onNodeWithTag("comparison_option_Z26").assertIsDisplayed().performClick()
        compose.onNodeWithTag("comparison_apply").performClick()
        compose.waitUntil(10_000) { compose.onAllNodesWithTag("comparison_header_2").fetchSemanticsNodes().isNotEmpty() }
    }
}
