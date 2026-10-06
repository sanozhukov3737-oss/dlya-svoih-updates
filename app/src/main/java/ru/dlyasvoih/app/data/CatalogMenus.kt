package ru.dlyasvoih.app.data

import ru.dlyasvoih.app.data.local.*

sealed interface CatalogMenuLoad {
    data object Loading : CatalogMenuLoad
    data object Error : CatalogMenuLoad
    data class Ready(val value: CatalogMenus) : CatalogMenuLoad
}

/** One shared, small catalog snapshot. No article bodies, images or user history. */
data class CatalogMenus(
    val categories: List<CategoryEntity>,
    val sectionCounts: Map<String, Int>,
    val categoryCounts: Map<String, Int>,
    val countries: List<CountryEntity>,
    val countryTotals: List<MenuCountryTotal>,
    val contentVersion: String = ""
) {
    fun categoriesFor(section: String) = categories.filter { section.isEmpty() || it.section == section }

    fun total(section: String, category: String): Int =
        if (category.isEmpty()) {
            if (section.isEmpty()) sectionCounts.values.sum() else sectionCounts[section] ?: 0
        } else if (categories.any { it.id == category && (section.isEmpty() || it.section == section) }) {
            categoryCounts[category] ?: 0
        } else 0

    fun countryChoices(section: String, category: String): List<CountryCount> {
        val names = countries.associateBy { it.id }
        return countryTotals.asSequence()
            .filter { (section.isEmpty() || it.section == section) && (category.isEmpty() || it.categoryId == category) }
            .groupBy { it.countryId }.mapNotNull { (id, rows) ->
                if (id == CountrySelection.USSR_AND_RUSSIA) {
                    CountryCount(id, "СССР / Россия", -1, rows.sumOf { it.total })
                } else names[id]?.let { CountryCount(id, it.name, it.sortOrder, rows.sumOf { row -> row.total }) }
            }.sortedWith(compareBy<CountryCount> { it.sortOrder }.thenBy { it.id })
    }
}
