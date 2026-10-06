# Room schema exports

SQL schema version: 3. KSP exports the actual Room JSON schemas to this directory during a successful Android build. No generated JSON or Room identity hash is claimed until Android compilation runs.

The v1 database fixture in app/src/androidTest/assets/database/v1.db comes from the unchanged v0.2 source. MigrationAndPagingTest opens it through the explicit 1→2→3 migrations; PackagedDatabaseTest compares the bundled v3 database with a fresh database created by generated Room code. Run these Android tests before releasing an APK.
