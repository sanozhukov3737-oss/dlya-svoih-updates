package ru.dlyasvoih.app.data.local

import androidx.room.*

@Entity(tableName = "countries")
data class CountryEntity(@PrimaryKey val id: String, val name: String, val sortOrder: Int)

@Entity(tableName = "categories")
data class CategoryEntity(@PrimaryKey val id: String, val section: String, val title: String, val sortOrder: Int)

@Entity(
    tableName = "cards",
    foreignKeys = [ForeignKey(entity = CategoryEntity::class, parentColumns = ["id"], childColumns = ["categoryId"], onDelete = ForeignKey.RESTRICT)],
    indices = [Index(value = ["id"], unique = true), Index(value = ["categoryId", "sortTitle", "rowid"]),
        Index(value = ["section", "sortTitle", "rowid"]), Index(value = ["sortTitle", "rowid"])]
)
data class CardEntity(
    @PrimaryKey @ColumnInfo(name = "rowid") val rowId: Long,
    val id: String, val section: String, val categoryId: String,
    val title: String, val summary: String, val body: String, val tags: String,
    val sortTitle: String, val searchText: String, val thumbnailPath: String?,
    val contentStatus: String, val reviewedAt: String?,
    @ColumnInfo(defaultValue = "0") val archived: Boolean = false,
    @ColumnInfo(defaultValue = "'legacy-reviewed'") val modelStatus: String = "legacy-reviewed",
    @ColumnInfo(defaultValue = "'legacy'") val sourceGrade: String = "legacy",
    val verifiedAt: String? = null
)

@Fts4(contentEntity = CardEntity::class, tokenizer = FtsOptions.TOKENIZER_UNICODE61)
@Entity(tableName = "cards_fts")
data class CardFtsEntity(val searchText: String)

@Entity(tableName = "card_countries", primaryKeys = ["cardId", "countryId"],
    foreignKeys = [
        ForeignKey(entity = CardEntity::class, parentColumns = ["id"], childColumns = ["cardId"], onDelete = ForeignKey.CASCADE),
        ForeignKey(entity = CountryEntity::class, parentColumns = ["id"], childColumns = ["countryId"], onDelete = ForeignKey.RESTRICT)],
    indices = [Index(value = ["countryId", "cardId"])])
data class CardCountryEntity(val cardId: String, val countryId: String)

@Entity(tableName = "images",
    foreignKeys = [ForeignKey(entity = CardEntity::class, parentColumns = ["id"], childColumns = ["cardId"], onDelete = ForeignKey.CASCADE)],
    indices = [Index(value = ["cardId", "position"])])
data class ImageEntity(@PrimaryKey val id: String, val cardId: String, val localPath: String,
    val caption: String, val width: Int, val height: Int, val position: Int)

@Entity(tableName = "sources",
    foreignKeys = [ForeignKey(entity = CardEntity::class, parentColumns = ["id"], childColumns = ["cardId"], onDelete = ForeignKey.CASCADE)],
    indices = [Index(value = ["cardId"])])
data class SourceEntity(@PrimaryKey val id: String, val cardId: String, val title: String,
    val url: String?, val accessedAt: String?)

@Entity(tableName = "favorites",
    foreignKeys = [ForeignKey(entity = CardEntity::class, parentColumns = ["id"], childColumns = ["cardId"], onDelete = ForeignKey.CASCADE)],
    indices = [Index(value = ["savedAt", "cardId"])])
data class FavoriteEntity(@PrimaryKey val cardId: String, val savedAt: Long)

@Entity(tableName = "metadata")
data class MetadataEntity(@PrimaryKey val key: String, val value: String)

@Entity(tableName = "reading", foreignKeys = [ForeignKey(entity = CardEntity::class,
    parentColumns = ["id"], childColumns = ["cardId"], onDelete = ForeignKey.CASCADE)],
    indices = [Index(value = ["updatedAt", "cardId"])])
data class ReadingEntity(@PrimaryKey val cardId: String, val itemIndex: Int,
    val offset: Int, val updatedAt: Long, val contentVersion: Long)

data class ContinueReading(val cardId: String, val title: String)

data class CardPreview(val id: String, val section: String, val title: String,
    val summary: String, val thumbnailPath: String?, val categoryId: String = "",
    val contentStatus: String = "demo", val modelStatus: String = "legacy-reviewed")

data class SectionCount(val section: String, val total: Int)

/** Lightweight menu metadata; article bodies stay in paged/detail queries. */
data class CountryCount(val id: String, val name: String, val sortOrder: Int, val total: Int)
data class CategoryCount(val categoryId: String, val total: Int)
data class MenuCountryTotal(val section: String, val categoryId: String, val countryId: String, val total: Int)
data class ReaderCard(val id: String, val title: String)
