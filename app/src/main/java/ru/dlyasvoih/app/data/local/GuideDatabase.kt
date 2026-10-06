package ru.dlyasvoih.app.data.local

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase
import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase

@Database(entities = [CountryEntity::class, CategoryEntity::class, CardEntity::class,
    CardFtsEntity::class, CardCountryEntity::class, ImageEntity::class, SourceEntity::class,
    FavoriteEntity::class, MetadataEntity::class, ReadingEntity::class], version = 3, exportSchema = true)
abstract class GuideDatabase : RoomDatabase() {
    abstract fun guideDao(): GuideDao

    companion object {
        val MIGRATION_1_2 = object : Migration(1, 2) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL("ALTER TABLE cards ADD COLUMN archived INTEGER NOT NULL DEFAULT 0")
                db.execSQL("CREATE TABLE IF NOT EXISTS reading (cardId TEXT NOT NULL PRIMARY KEY, itemIndex INTEGER NOT NULL, offset INTEGER NOT NULL, updatedAt INTEGER NOT NULL, contentVersion INTEGER NOT NULL, FOREIGN KEY(cardId) REFERENCES cards(id) ON UPDATE NO ACTION ON DELETE CASCADE)")
                db.execSQL("CREATE INDEX IF NOT EXISTS index_reading_updatedAt_cardId ON reading(updatedAt, cardId)")
            }
        }

        val MIGRATION_2_3 = object : Migration(2, 3) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL("ALTER TABLE cards ADD COLUMN modelStatus TEXT NOT NULL DEFAULT 'legacy-reviewed'")
                db.execSQL("ALTER TABLE cards ADD COLUMN sourceGrade TEXT NOT NULL DEFAULT 'legacy'")
                db.execSQL("ALTER TABLE cards ADD COLUMN verifiedAt TEXT")
            }
        }

        fun create(context: Context, name: String = "guide.db"): GuideDatabase =
            Room.databaseBuilder(context.applicationContext, GuideDatabase::class.java, name)
                .createFromAsset("database/guide-v29.db")
                .addMigrations(MIGRATION_1_2, MIGRATION_2_3)
                .setJournalMode(RoomDatabase.JournalMode.WRITE_AHEAD_LOGGING)
                .build()
        // Future schema changes require explicit tested migrations. Never delete user data.
    }
}
