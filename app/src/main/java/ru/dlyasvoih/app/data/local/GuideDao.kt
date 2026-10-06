package ru.dlyasvoih.app.data.local

import androidx.paging.PagingSource
import androidx.room.*
import androidx.sqlite.db.SupportSQLiteQuery
import kotlinx.coroutines.flow.Flow

@Dao
interface GuideDao {
    @RawQuery
    suspend fun cardIds(query: SupportSQLiteQuery): List<String>
    @RawQuery
    suspend fun readerCards(query: SupportSQLiteQuery): List<ReaderCard>

    @RawQuery(observedEntities = [CardEntity::class, CardFtsEntity::class, CardCountryEntity::class, ReadingEntity::class])
    fun page(query: SupportSQLiteQuery): PagingSource<Int, CardPreview>

    @RawQuery(observedEntities = [CardEntity::class, CardFtsEntity::class, FavoriteEntity::class, CardCountryEntity::class])
    fun favoritePage(query: SupportSQLiteQuery): PagingSource<Int, CardPreview>

    @Query("SELECT cardId FROM favorites WHERE cardId IN (:ids)")
    fun favoritesFor(ids: List<String>): Flow<List<String>>

    @Query("SELECT * FROM cards WHERE id = :id") fun card(id: String): Flow<CardEntity?>
    @Query("SELECT * FROM images WHERE cardId = :id ORDER BY position, id") fun images(id: String): Flow<List<ImageEntity>>
    @Query("SELECT * FROM sources WHERE cardId = :id ORDER BY id") fun sources(id: String): Flow<List<SourceEntity>>
    @Query("SELECT * FROM countries ORDER BY sortOrder, id") fun countries(): Flow<List<CountryEntity>>
    @Query("SELECT co.* FROM countries co JOIN card_countries cc ON cc.countryId = co.id WHERE cc.cardId = :id ORDER BY co.sortOrder")
    fun cardCountries(id: String): Flow<List<CountryEntity>>
    @Query("SELECT * FROM categories WHERE (:section = '' OR section = :section) ORDER BY sortOrder, id")
    fun categories(section: String): Flow<List<CategoryEntity>>
    // Catalog navigation never depends on favorites or reading writes. Count each linked
    // card once in the combined USSR/Russia group, including cards linked to both countries.
    @Query("""
        SELECT c.section, c.categoryId, cc.countryId, COUNT(*) AS total
        FROM cards c JOIN card_countries cc ON cc.cardId = c.id
        WHERE c.archived = 0 AND cc.countryId NOT IN ('su', 'ru')
        GROUP BY c.section, c.categoryId, cc.countryId
        UNION ALL
        SELECT c.section, c.categoryId, '@ru-su' AS countryId, COUNT(DISTINCT c.id) AS total
        FROM cards c JOIN card_countries cc ON cc.cardId = c.id
        WHERE c.archived = 0 AND cc.countryId IN ('su', 'ru')
        GROUP BY c.section, c.categoryId
    """)
    fun menuCountryTotals(): Flow<List<MenuCountryTotal>>
    @Query("""
        SELECT co.id, co.name, co.sortOrder, COUNT(DISTINCT c.id) AS total
        FROM countries co
        JOIN card_countries cc ON cc.countryId = co.id
        JOIN cards c ON c.id = cc.cardId
        WHERE ((:favoritesOnly = 0 AND c.archived = 0)
            OR (:favoritesOnly = 1 AND EXISTS (SELECT 1 FROM favorites f WHERE f.cardId = c.id)))
            AND (:historyOnly = 0 OR EXISTS (SELECT 1 FROM reading r WHERE r.cardId = c.id))
            AND (:section = '' OR c.section = :section)
            AND (:category = '' OR c.categoryId = :category)
            AND co.id NOT IN ('su', 'ru')
        GROUP BY co.id, co.name, co.sortOrder
        UNION ALL
        SELECT '@ru-su' AS id, 'СССР / Россия' AS name, -1 AS sortOrder, COUNT(DISTINCT c.id) AS total
        FROM cards c
        JOIN card_countries cc ON cc.cardId = c.id
        WHERE ((:favoritesOnly = 0 AND c.archived = 0)
            OR (:favoritesOnly = 1 AND EXISTS (SELECT 1 FROM favorites f WHERE f.cardId = c.id)))
            AND (:historyOnly = 0 OR EXISTS (SELECT 1 FROM reading r WHERE r.cardId = c.id))
            AND (:section = '' OR c.section = :section)
            AND (:category = '' OR c.categoryId = :category)
            AND cc.countryId IN ('su', 'ru')
        GROUP BY 1, 2, 3
        ORDER BY sortOrder, id
    """)
    fun countryChoices(section: String, category: String, favoritesOnly: Boolean = false,
        historyOnly: Boolean = false): Flow<List<CountryCount>>
    @Query("""
        SELECT COUNT(*) FROM cards
        WHERE archived = 0 AND (:section = '' OR section = :section)
            AND (:category = '' OR categoryId = :category)
    """)
    fun categoryCardCount(section: String, category: String): Flow<Int>
    @Query("SELECT categoryId, COUNT(*) AS total FROM cards WHERE archived = 0 GROUP BY categoryId")
    fun categoryCounts(): Flow<List<CategoryCount>>
    @Query("SELECT section, COUNT(*) AS total FROM cards WHERE archived = 0 GROUP BY section") fun sectionCounts(): Flow<List<SectionCount>>
    @Query("SELECT EXISTS(SELECT 1 FROM favorites WHERE cardId = :id)") fun isFavorite(id: String): Flow<Boolean>
    @Query("SELECT EXISTS(SELECT 1 FROM cards WHERE id = :id)") suspend fun hasCard(id: String): Boolean
    @Query("DELETE FROM favorites WHERE cardId = :id") suspend fun removeFavorite(id: String): Int
    @Insert(onConflict = OnConflictStrategy.IGNORE) suspend fun addFavorite(favorite: FavoriteEntity)
    @Query("SELECT value FROM metadata WHERE `key` = :key") suspend fun metadata(key: String): String?
    @Query("SELECT value FROM metadata WHERE `key` = :key") fun observeMetadata(key: String): Flow<String?>
    @Insert(onConflict = OnConflictStrategy.REPLACE) suspend fun putMetadata(value: MetadataEntity)

    @Query("SELECT * FROM reading WHERE cardId = :id") suspend fun reading(id: String): ReadingEntity?
    @Query("SELECT r.cardId, c.title FROM reading r JOIN cards c ON c.id = r.cardId ORDER BY r.updatedAt DESC, r.cardId LIMIT 1")
    fun continueReading(): Flow<ContinueReading?>
    // One-shot exports for the backup screen. archived cards are kept in the join deliberately:
    // a favorited or read card that later left the catalog still has a row here and a title to show.
    @Query("SELECT f.cardId, c.title FROM favorites f JOIN cards c ON c.id = f.cardId ORDER BY f.savedAt DESC")
    suspend fun allFavorites(): List<ContinueReading>
    @Query("SELECT r.cardId, c.title FROM reading r JOIN cards c ON c.id = r.cardId ORDER BY r.updatedAt DESC")
    suspend fun allReading(): List<ContinueReading>
    @Query("""
        SELECT c.id, c.section, c.title, c.summary, c.thumbnailPath, c.categoryId,
            c.contentStatus, c.modelStatus
        FROM reading r JOIN cards c ON c.id = r.cardId
        WHERE c.archived = 0
        ORDER BY r.updatedAt DESC, r.cardId LIMIT 6
    """)
    fun recentCards(): Flow<List<CardPreview>>
    @Query("""
        SELECT c.id, c.section, c.title, c.summary, c.thumbnailPath, c.categoryId,
            c.contentStatus, c.modelStatus
        FROM favorites f JOIN cards c ON c.id = f.cardId
        WHERE c.archived = 0
        ORDER BY f.savedAt DESC, f.cardId LIMIT 6
    """)
    fun favoritePreviews(): Flow<List<CardPreview>>
    @Query("""
        SELECT c.id, c.section, c.title, c.summary, c.thumbnailPath, c.categoryId,
            c.contentStatus, c.modelStatus
        FROM cards c
        WHERE c.archived = 0 AND c.id != :id
            AND c.categoryId = (SELECT categoryId FROM cards WHERE id = :id)
        ORDER BY c.sortTitle, c.rowid LIMIT 12
    """)
    fun relatedCards(id: String): Flow<List<CardPreview>>
    @Query("""
        SELECT c.* FROM cards c
        WHERE c.archived = 0 AND c.id != :id
            AND c.categoryId = (SELECT categoryId FROM cards WHERE id = :id)
        ORDER BY c.sortTitle, c.rowid LIMIT 12
    """)
    fun relatedCardEntities(id: String): Flow<List<CardEntity>>
    @Upsert suspend fun saveReading(value: ReadingEntity)
    @Query("DELETE FROM reading WHERE cardId = :id") suspend fun removeReading(id: String): Int
    @Query("DELETE FROM reading WHERE cardId NOT IN (SELECT cardId FROM reading ORDER BY updatedAt DESC, cardId LIMIT 50)")
    suspend fun trimReading()

    @Upsert suspend fun putCountries(values: List<CountryEntity>)
    @Upsert suspend fun putCategories(values: List<CategoryEntity>)
    @Upsert suspend fun putCard(value: CardEntity)
    @Insert suspend fun putImages(values: List<ImageEntity>)
    @Insert suspend fun putSources(values: List<SourceEntity>)
    @Insert suspend fun putCardCountries(values: List<CardCountryEntity>)
    @Query("SELECT id FROM cards WHERE rowid = :rowId") suspend fun idForRow(rowId: Long): String?
    @Query("SELECT rowid FROM cards WHERE id = :id") suspend fun rowForId(id: String): Long?
    @Query("UPDATE cards SET archived = 1") suspend fun archiveCards()
    @Query("DELETE FROM images WHERE cardId = :id") suspend fun clearImages(id: String)
    @Query("DELETE FROM sources WHERE cardId = :id") suspend fun clearSources(id: String)
    @Query("DELETE FROM card_countries WHERE cardId = :id") suspend fun clearCardCountries(id: String)
    @Query("DELETE FROM cards WHERE archived = 1 AND id NOT IN (SELECT cardId FROM favorites) AND id NOT IN (SELECT cardId FROM reading)")
    suspend fun pruneArchived()
    @Query("SELECT DISTINCT localPath FROM images WHERE localPath LIKE 'packs/%' UNION SELECT DISTINCT thumbnailPath FROM cards WHERE thumbnailPath LIKE 'packs/%'")
    suspend fun usedMedia(): List<String>
}
