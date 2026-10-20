# RECOVERY STAGE 1 — повторная сверка восстановленного комплекта

20.10.2026. Текущее дерево: `/workspace/scratch/a8009b11e95e/source134`. Репозиторий: `sanozhukov3737-oss/dlya-svoih-updates`. Старый путь `/workspace/scratch/624b24ec03db/dlya-svoih-uav-reference` в текущей среде отсутствует; его наличие не предполагается.

Прочитаны `AGENTS.md`, `OFFLINE_3D.md`, `research/release-0.3.134.md`, `research/release-0.3.134-validation.json`. Комплекты восстановлены и проверены заново по реальным файлам.

| Входной файл | Путь | Размер, байт | SHA-256 |
| --- | --- | ---: | --- |
| Кандидат | `/workspace/scratch/a8009b11e95e/recovered134/DLYA_SVOIH_COMBINED_0.3.134_CANDIDATE.zip` | 154986054 | `4d4ea41cf03a341f7def67fda7d9238440fd9947b0a2b03cf403890577b0e8c1` |
| Прежний комплект подписи | `/workspace/scratch/a8009b11e95e/recovered134/DLYA_SVOIH_SIGN_0.3.134_STAGE3.zip` | 262233114 | `014a634b3c8e08267f76802b0e787c221a8541ca7fdb06011b8a3d51d97881a0` |
| Исходный unsigned APK | `/workspace/scratch/a8009b11e95e/recovered134/candidate/DLYA_SVOIH_v0.3.134-unsigned.apk` | 144614177 | `43ffc8b8d8ba2a632d3d13a5f287a4fb6a6a43bddf008122026186aa2a0197f4` |
| Старый source bundle | `/workspace/scratch/a8009b11e95e/recovered134/candidate/DLYA_SVOIH_0.3.134.bundle` | 12362857 | `17f54a6770eb980241edd5fd2ac356b93cda4785bac3b708bcda9c6d8d078104` |

Bundle восстановлен на коммите `e5eb15076c4727ec0deb32a4f7b2ac43b1e3b812`; необходимая база — опубликованный `app-0.3.133`, `adca80ea2c8076bde6b8f5ee0a3f8e48250bc972`. `git bundle verify` прошёл. Важное расхождение: bundle содержит исходную базу 188 на 1595 карточек, тогда как APK содержит актуальную базу 195 на 1697 карточек и 1600 изображений. Поэтому один старый bundle не является полным текущим комплектом ресурсов.

В рабочие исходники восстановлены 626 ресурсов из проверенного APK; два создаваемых сборкой профиля dexopt исключены. Затем исправлены пять поисковых полей, отклонённых настоящим Android-валидатором импорта. Полное дерево данных зафиксировано коммитом `e920f5a6068f0a0ce0efa54f082a97cb15e85516`, ветка `recovery/complete-0.3.134-20261020`. История и точные хеши каждого восстановленного ресурса — `research/recovery-stage-3/source-assets-restoration.json`. `content/catalog.json` остаётся старым редактируемым источником 188; им нельзя перегенерировать полный production-каталог 195.

Подтверждены наличие и размер APK, пакет `ru.dlyasvoih.app`, versionName `0.3.134`, versionCode `138`, debuggable=false. В APK — 19 GLB с совпадающими хешами манифеста, авторством, лицензиями и режимом окраски; все 3106 уникальных ссылок на медиа разрешаются. Все 1426 опубликованных ID/rowid и 2624 прежних файлов изображений/миниатюр сохранены. База проходит integrity_check и foreign_key_check. Полный набор даёт 102 карточки сверх старого дерева bundle; точная сверка ID, включая пять source-only ID, отсутствовавших в подготовленном APK, сохранена в `catalog-restoration-check.json`. Все опубликованные карточки присутствуют.

Актуальный исправленный подписанный APK: `/workspace/scratch/a8009b11e95e/source134/build/recovery-stage3/signed-shader-fixed/DLYA_SVOIH_v0.3.134.apk`, 144646769 байт, SHA-256 `300b77deaee3348e05a0135bf0079414c07dc2e15a7dcfd9b1239a8cef99298f`. Его база имеет SHA-256 `fbbb7a38d77b09b963520011ef64b8111991e03ed1b2ae6277ec335761a107ed`. Коммит приложения с полными ресурсами и окончательным исправлением шейдера — `a8c3b76f8921ffe05e4beaad7b6ba33891200642`. Все 3640 production-assets в отслеживаемом дереве совпадают с окончательным APK, лишних отслеживаемых assets нет; протокол — `research/recovery-stage-3/source-apk-assets-comparison.json`.

Итоговый полный комплект: `/workspace/scratch/a8009b11e95e/source134/build/recovery-stage3/DLYA_SVOIH_0.3.134_RECOVERY_COMPLETE.zip`. В нём самодостаточный Git bundle с полной историей ветки, отчёты и Android-доказательства. Точный коммит отчётов, размер и SHA-256 bundle и архива записаны в соседнем `DLYA_SVOIH_0.3.134_HANDOFF.json`; отдельный `RECOVERY_HANDOFF.json` внутри ZIP фиксирует bundle. Хеш внешнего архива не помещается внутрь самого архива. Старый CANDIDATE/bundle и промежуточные SIGNED_FIXED/SIGNED_RENDER_FIXED не являются итоговым комплектом.

Подпись и Android-результаты относятся к последующим этапам: [RECOVERY-STAGE-2.md](RECOVERY-STAGE-2.md), [RECOVERY-STAGE-3.md](RECOVERY-STAGE-3.md). Архивы прежних этапов не подменяют актуальный исправленный APK. Публикация приложения и переключение канала обновлений не выполнялись.
