package ru.dlyasvoih.app.data

object SearchQuery {
    const val MAX_LENGTH = 160
    fun normalize(value: String): String = CatalogSearch.normalize(value)
    fun match(value: String): String? = CatalogSearch.match(value)
    fun key(value: String): String = match(value) ?: if (value.isBlank()) "" else "!empty"
}

data class CatalogFilter(
    val section: String = "",
    val category: String = "",
    val country: String = "",
    val query: String = "",
    val favoritesOnly: Boolean = false,
    val historyOnly: Boolean = false,
    val status: String = "",
    val photo: String = ""
)

object CatalogStatus {
    const val VERIFIED = "verified"
    const val REVIEWED = "reviewed"
    const val SOURCE_ONLY = "source_only"
    const val CANDIDATE = "candidate"
}

object PhotoSelection {
    const val WITH_PHOTO = "with-photo"
    const val WITHOUT_PHOTO = "without-photo"
}

object CountrySelection {
    const val USSR_AND_RUSSIA = "@ru-su"
}

data class SqlRequest(val sql: String, val args: List<Any>)

object CatalogQuery {
    // Lists fetch short previews only. Full article bodies are loaded by card id.
    const val PROJECTION = """SELECT c.id, c.section, c.title, c.summary, c.thumbnailPath, c.categoryId, c.contentStatus, c.modelStatus FROM cards c"""

    fun build(filter: CatalogFilter): SqlRequest = build(filter, PROJECTION)

    // The book keeps the complete ordered ID list, not the bounded preview Paging window.
    // Both modes use exactly the same filters and sort order.
    fun ids(filter: CatalogFilter): SqlRequest = build(filter, "SELECT c.id FROM cards c")
    fun readerCards(filter: CatalogFilter): SqlRequest = build(filter, "SELECT c.id, c.title FROM cards c")

    private fun build(filter: CatalogFilter, projection: String): SqlRequest {
        val args = mutableListOf<Any>()
        val conditions = mutableListOf<String>()
        val sql = StringBuilder(projection)
        val search = CatalogSearch.plan(filter.query)
        if (search != null) {
            conditions += search.whereSql
            args.addAll(search.whereArgs)
        } else if (filter.query.isNotBlank()) {
            conditions += "0 = 1"
        }
        require(!(filter.favoritesOnly && filter.historyOnly))
        when {
            filter.favoritesOnly -> sql.append(" JOIN favorites saved ON saved.cardId = c.id")
            filter.historyOnly -> sql.append(" JOIN reading history ON history.cardId = c.id")
            else -> Unit
        }
        conditions += "c.archived = 0"
        if (filter.section.isNotEmpty()) { conditions += "c.section = ?"; args += filter.section }
        if (filter.category.isNotEmpty()) { conditions += "c.categoryId = ?"; args += filter.category }
        if (filter.country == CountrySelection.USSR_AND_RUSSIA) {
            conditions += "c.id IN (SELECT cardId FROM card_countries WHERE countryId IN (?, ?))"
            args += "su"
            args += "ru"
        } else if (filter.country.isNotEmpty()) {
            conditions += "c.id IN (SELECT cardId FROM card_countries WHERE countryId = ?)"
            args += filter.country
        }
        when (filter.status) {
            CatalogStatus.VERIFIED -> conditions += "c.modelStatus LIKE 'verified-%' AND c.contentStatus != 'candidate'"
            CatalogStatus.REVIEWED -> conditions += "c.contentStatus = 'reviewed'"
            CatalogStatus.SOURCE_ONLY -> conditions += "c.contentStatus = 'source_only'"
            CatalogStatus.CANDIDATE -> conditions += "c.contentStatus IN ('candidate', 'medical_review_required')"
        }
        when (filter.photo) {
            PhotoSelection.WITH_PHOTO -> conditions += "EXISTS (SELECT 1 FROM images picture WHERE picture.cardId = c.id)"
            PhotoSelection.WITHOUT_PHOTO -> conditions += "NOT EXISTS (SELECT 1 FROM images picture WHERE picture.cardId = c.id)"
        }
        if (conditions.isNotEmpty()) sql.append(" WHERE ").append(conditions.joinToString(" AND "))
        val order = when {
            filter.favoritesOnly -> "saved.savedAt DESC, c.rowid DESC"
            filter.historyOnly -> "history.updatedAt DESC, c.rowid DESC"
            else -> "c.sortTitle, c.rowid"
        }
        if (search != null) {
            sql.append(" ORDER BY ").append(search.rankSql).append(", ").append(order)
            args.addAll(search.rankArgs)
        } else sql.append(" ORDER BY ").append(order)
        return SqlRequest(sql.toString(), args)
    }
}
