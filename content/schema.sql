PRAGMA foreign_keys = ON;
PRAGMA user_version = 3;
CREATE TABLE countries (id TEXT NOT NULL PRIMARY KEY, name TEXT NOT NULL, sortOrder INTEGER NOT NULL);
CREATE TABLE categories (id TEXT NOT NULL PRIMARY KEY, section TEXT NOT NULL, title TEXT NOT NULL, sortOrder INTEGER NOT NULL);
CREATE TABLE cards (
    rowid INTEGER NOT NULL PRIMARY KEY,
    id TEXT NOT NULL, section TEXT NOT NULL, categoryId TEXT NOT NULL,
    title TEXT NOT NULL, summary TEXT NOT NULL, body TEXT NOT NULL, tags TEXT NOT NULL,
    sortTitle TEXT NOT NULL, searchText TEXT NOT NULL, thumbnailPath TEXT,
    contentStatus TEXT NOT NULL, reviewedAt TEXT, archived INTEGER NOT NULL DEFAULT 0,
    modelStatus TEXT NOT NULL DEFAULT 'legacy-reviewed',
    sourceGrade TEXT NOT NULL DEFAULT 'legacy', verifiedAt TEXT,
    FOREIGN KEY(categoryId) REFERENCES categories(id) ON UPDATE NO ACTION ON DELETE RESTRICT
);
CREATE UNIQUE INDEX index_cards_id ON cards(id);
CREATE INDEX index_cards_categoryId_sortTitle_rowid ON cards(categoryId, sortTitle, rowid);
CREATE INDEX index_cards_section_sortTitle_rowid ON cards(section, sortTitle, rowid);
CREATE INDEX index_cards_sortTitle_rowid ON cards(sortTitle, rowid);
CREATE VIRTUAL TABLE cards_fts USING FTS4(`searchText` TEXT NOT NULL, tokenize=unicode61, content=`cards`);
CREATE TRIGGER IF NOT EXISTS room_fts_content_sync_cards_fts_BEFORE_UPDATE BEFORE UPDATE ON cards BEGIN
    DELETE FROM cards_fts WHERE docid=OLD.rowid;
END;
CREATE TRIGGER IF NOT EXISTS room_fts_content_sync_cards_fts_BEFORE_DELETE BEFORE DELETE ON cards BEGIN
    DELETE FROM cards_fts WHERE docid=OLD.rowid;
END;
CREATE TRIGGER IF NOT EXISTS room_fts_content_sync_cards_fts_AFTER_UPDATE AFTER UPDATE ON cards BEGIN
    INSERT INTO cards_fts(docid, searchText) VALUES(NEW.rowid, NEW.searchText);
END;
CREATE TRIGGER IF NOT EXISTS room_fts_content_sync_cards_fts_AFTER_INSERT AFTER INSERT ON cards BEGIN
    INSERT INTO cards_fts(docid, searchText) VALUES(NEW.rowid, NEW.searchText);
END;
CREATE TABLE card_countries (
    cardId TEXT NOT NULL, countryId TEXT NOT NULL, PRIMARY KEY(cardId, countryId),
    FOREIGN KEY(cardId) REFERENCES cards(id) ON UPDATE NO ACTION ON DELETE CASCADE,
    FOREIGN KEY(countryId) REFERENCES countries(id) ON UPDATE NO ACTION ON DELETE RESTRICT
);
CREATE INDEX index_card_countries_countryId_cardId ON card_countries(countryId, cardId);
CREATE TABLE images (
    id TEXT NOT NULL PRIMARY KEY, cardId TEXT NOT NULL, localPath TEXT NOT NULL, caption TEXT NOT NULL,
    width INTEGER NOT NULL, height INTEGER NOT NULL, position INTEGER NOT NULL,
    FOREIGN KEY(cardId) REFERENCES cards(id) ON UPDATE NO ACTION ON DELETE CASCADE
);
CREATE INDEX index_images_cardId_position ON images(cardId, position);
CREATE TABLE sources (
    id TEXT NOT NULL PRIMARY KEY, cardId TEXT NOT NULL, title TEXT NOT NULL, url TEXT, accessedAt TEXT,
    FOREIGN KEY(cardId) REFERENCES cards(id) ON UPDATE NO ACTION ON DELETE CASCADE
);
CREATE INDEX index_sources_cardId ON sources(cardId);
CREATE TABLE favorites (
    cardId TEXT NOT NULL PRIMARY KEY, savedAt INTEGER NOT NULL,
    FOREIGN KEY(cardId) REFERENCES cards(id) ON UPDATE NO ACTION ON DELETE CASCADE
);
CREATE INDEX index_favorites_savedAt_cardId ON favorites(savedAt, cardId);
CREATE TABLE metadata (`key` TEXT NOT NULL PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE reading (cardId TEXT NOT NULL PRIMARY KEY, itemIndex INTEGER NOT NULL,
    offset INTEGER NOT NULL, updatedAt INTEGER NOT NULL, contentVersion INTEGER NOT NULL,
    FOREIGN KEY(cardId) REFERENCES cards(id) ON UPDATE NO ACTION ON DELETE CASCADE);
CREATE INDEX index_reading_updatedAt_cardId ON reading(updatedAt, cardId);
