# Обновление ТТХ v0.3.81

Проверены источники ещё 20 карточек боеприпасов. В 15 карточках добавлены числовые сведения с указанием исполнения и ограничений источника; в пяти уточнено отсутствие данных либо атрибуция. Добавлена 71 строка, включая сверку, и 7 новых разделов ТТХ. В 10 карточках добавлены сведения о массе основного наполнения, включая явно обозначенные противоречивые и общие справочные строки; это не 10 полностью подтверждённых паспортов.

Всего проверены источники 864 из 1287 карточек. Осталось 423: 380 боеприпасов, 6 ПТРК, 17 СВО и 20 медицинских карточек. Из оставшихся боеприпасов 87 пока без раздела ТТХ.

Разделены Mod морских мин, массы контейнера и вложенного изделия. Для SMArt 155 и Mk 67 явно отмечены расхождения единиц. Таблицы M821A1 / M889A1 не перенесены на E1; данные позднего M930 приведены отдельно от раннего XM930. Ограничения общей строки Type 72 и индексированного фрагмента XM1208 указаны в карточках.

Версия приложения 0.3.81, код 85, версия содержимого 123. База пересобрана; точное воспроизведение обновления и повторный запуск проверены, 15 локальных тестов пройдены. Сохранены прежние исправления открытия базы и карточек. APK здесь не собирался, запуск на Android не проверялся.

Из распакованной папки проекта в PowerShell:

```powershell
.\MAKE_APK.bat
explorer.exe ".\app\build\outputs\apk\debug"
```

## Карточки и источники

### Mk 36

ORD 696(B), 1959: Mod 1–3 разделены. Номинальный класс 1000 lb не равен полной массе. Пересчёт приблизительный; сведения других Mod не переносились.

- [U.S. Navy — ORD 696(B), 1959, печатная стр. 87: Mk 36 Mod 1](https://maritime.org/doc/mines-usn/img/pg087.jpg)
- [U.S. Navy — ORD 696(B), 1959, печатная стр. 91: Mk 36 Mod 2](https://maritime.org/doc/mines-usn/img/pg091.jpg)
- [U.S. Navy — ORD 696(B), 1959, печатная стр. 95: Mk 36 Mod 3](https://maritime.org/doc/mines-usn/img/pg095.jpg)

### Mk 52

ORD 696(B), 1959: семь Mod имеют разные полные массы. Класс 1000 lb не заменяет эти значения. Метрические значения рассчитаны отдельно.

- [U.S. Navy — ORD 696(B), 1959, печатная стр. 127: Mk 52 Mod 0](https://maritime.org/doc/mines-usn/img/pg127.jpg)
- [U.S. Navy — ORD 696(B), 1959, печатная стр. 131: Mk 52 Mod 1](https://maritime.org/doc/mines-usn/img/pg131.jpg)
- [U.S. Navy — ORD 696(B), 1959, печатная стр. 135: Mk 52 Mod 2](https://maritime.org/doc/mines-usn/img/pg135.jpg)
- [U.S. Navy — ORD 696(B), 1959, печатная стр. 139: Mk 52 Mod 3](https://maritime.org/doc/mines-usn/img/pg139.jpg)
- [U.S. Navy — ORD 696(B), 1959, печатная стр. 143: Mk 52 Mod 4](https://maritime.org/doc/mines-usn/img/pg143.jpg)
- [U.S. Navy — ORD 696(B), 1959, печатная стр. 147: Mk 52 Mod 5](https://maritime.org/doc/mines-usn/img/pg147.jpg)
- [U.S. Navy — ORD 696(B), 1959, печатная стр. 151: Mk 52 Mod 6](https://maritime.org/doc/mines-usn/img/pg151.jpg)

### Mk 56

Историческое значение; номер Mod не указан.

- [U.S. Navy — All Hands, January 2002, №1017, MINES, стр. 46–47: текст публичной копии](https://device.report/m/c18e2bbd12afe027d2a4b03b449fb40db25017ab56a868d77500f33b839dc71e)

### Mk 57

Историческое значение; номер Mod не указан.

- [U.S. Navy — All Hands, January 2002, №1017, MINES, стр. 46–47: текст публичной копии](https://device.report/m/c18e2bbd12afe027d2a4b03b449fb40db25017ab56a868d77500f33b839dc71e)

### Mk 60 Captor

Масса наполнения относится к торпеде, не к контейнеру. Прежние 1184 / 1075 кг сохранены отдельно; комплектации источников расходятся.

- [U.S. Navy — All Hands, January 2002, №1017, MINES, стр. 46–47: текст публичной копии](https://device.report/m/c18e2bbd12afe027d2a4b03b449fb40db25017ab56a868d77500f33b839dc71e)

### Mk 67 SLMM

Пара полной массы в публикации расходится: 1658 lb ≈752,06 кг, а не 754 кг. Для основного наполнения 330 lb ≈149,69 кг; опубликованные 150 кг округлены. 13,4 ft ≈4084,3 мм; 19 in =482,6 мм. Прежние 4090 / 485 мм сохранены по своему источнику.

- [U.S. Navy — All Hands, January 2002, №1017, MINES, стр. 46–47: текст публичной копии](https://device.report/m/c18e2bbd12afe027d2a4b03b449fb40db25017ab56a868d77500f33b839dc71e)

### L14

Историческая сводная строка, не отдельный британский заводской паспорт. Значения не назначены всем вариантам L14.

- [U.S. Army / TRADOC — WEG 2015, Vol. 1, PDF-стр. 463: MIACAH F1 / L14A1](https://upload.wikimedia.org/wikipedia/commons/1/1f/WorldwideEquipmentGuide_2015_Ground_Systems.pdf)

### Type 72 AT (ЮАР)

WEG объединяет страны в одну строку. Независимый паспорт именно южноафриканского исполнения не установлен; эти числа не являются его отдельной заводской аттестацией. Type 72 AP отделена.

- [U.S. Army / TRADOC — WEG 2015, Vol. 1, PDF-стр. 457–458: Type 72 AT](https://upload.wikimedia.org/wikipedia/commons/1/1f/WorldwideEquipmentGuide_2015_Ground_Systems.pdf)

### SMArt 155 — 155-мм артиллерийский снаряд

Не выбрано одно число вместо другого. Марка ВВ и распределение массы между суббоеприпасами не раскрыты. В той же брошюре 35 in и 898 мм также не совпадают: 35 in =889 мм; прежние 898 мм сохранены как метрическое поле источника.

- [GD-OTS — SMArt 155, заводская брошюра, стр. 2, Characteristics](https://www.gdots.com/wp-content/uploads/2017/11/SMArt155.pdf)

### K307 — 155-мм осколочно-фугасный снаряд

Длина явно дана со взрывателем. Поле Weight не поясняет включение взрывателя в массу; прежнее ограничение сохранено.

- [KOTRA — Korea Defense Products Guide 2019, Poongsan, печатная стр. 46 / PDF-стр. 44](https://www.kotra.or.kr/kodits/upload_file/promotion/2019%20Korea%20Defense%20Products%20Guide.pdf)

### M395 — 155-мм кассетный артиллерийский снаряд

Это сведения о снаряде-носителе. Масса отдельного M85 не умножалась для получения массы всего снаряда или наполнения.

- [King, Dullum, Østern — M85: an analysis of reliability, 2007, Annex A, стр. 44 / PDF-стр. 44](https://www.clusterconvention.org/files/external_publications/m85.pdf)

### M396 — 155-мм кассетный артиллерийский снаряд

Это сведения о снаряде-носителе. Масса отдельного M85 не умножалась для получения массы всего снаряда или наполнения.

- [King, Dullum, Østern — M85: an analysis of reliability, 2007, Annex A, стр. 44 / PDF-стр. 44](https://www.clusterconvention.org/files/external_publications/m85.pdf)

### M139 Volcano — система рассеивания мин

Разделены система, контейнер и две категории мин. Масса наполнения не заменяет полную массу; числа не назначены всем вариантам M87.

- [GICHD — Explosive Ordnance Guide for Ukraine, Third Edition, 2025, стр. 45](https://www.gichd.org/fileadmin/user_upload/Explosive_Ordnance_Guide_for_Ukraine__GICHD_-_Third_edition__v06_WEB.pdf)

### 81 мм M821E1

ARDEC прямо различает E1 и исходную модель. В оглавлении открытой копии TM 43-0001-28 встречается E1, но соответствующий лист подписан A1; его числа не перенесены на E1.

- [U.S. Army ARDEC — Circular 70-1, M821E1 / M889E1, печатная стр. 15 / PDF-стр. 26](https://www.bulletpicker.com/pdf/ARDEC-Circular-70-1.pdf)
- [U.S. Army — TM 43-0001-28, листы 4-75–76 и 4-81: разграничение E1 в оглавлении и A1 в заголовке](https://www.bulletpicker.com/pdf/TM-43-0001-28-1994.pdf)

### 81 мм M889E1

ARDEC прямо различает E1 и исходную модель. В оглавлении открытой копии TM 43-0001-28 встречается E1, но соответствующий лист подписан A1; его числа не перенесены на E1.

- [U.S. Army ARDEC — Circular 70-1, M821E1 / M889E1, печатная стр. 15 / PDF-стр. 26](https://www.bulletpicker.com/pdf/ARDEC-Circular-70-1.pdf)
- [U.S. Army — TM 43-0001-28, листы 4-75–76 и 4-81: разграничение E1 в оглавлении и A1 в заголовке](https://www.bulletpicker.com/pdf/TM-43-0001-28-1994.pdf)

### 120 мм XM930

Лист Change 11 подписан M930, а не XM930. Данные позднего исполнения выделены отдельно; не заменяют паспорт раннего XM930. Внутренние инициирующие элементы не добавлялись.

- [U.S. Army — TM 43-0001-28, Change 11, лист 4-115 / PDF-стр. 530: M930](https://www.bulletpicker.com/pdf/TM-43-0001-28-1994.pdf)

### АВУ

Таблица GICHD содержит общий размерный блок 658×598×191 мм без пояснения комплектации; он не принят за размеры отдельного металлического взрывателя.

- [GICHD — Explosive Ordnance Guide for Ukraine, Third Edition, 2025, стр. 245](https://www.gichd.org/fileadmin/user_upload/Explosive_Ordnance_Guide_for_Ukraine__GICHD_-_Third_edition__v06_WEB.pdf)

### 9Э246М

Поля Unknown не заменены нулём. Масса и размеры соседнего взрывателя или суббоеприпаса не переносились.

- [GICHD — Explosive Ordnance Guide for Ukraine, Third Edition, 2025, стр. 248](https://www.gichd.org/fileadmin/user_upload/Explosive_Ordnance_Guide_for_Ukraine__GICHD_-_Third_edition__v06_WEB.pdf)

### 9Э272

Поля Unknown не заменены нулём. Масса и размеры соседнего взрывателя или суббоеприпаса не переносились.

- [GICHD — Explosive Ordnance Guide for Ukraine, Third Edition, 2025, стр. 249](https://www.gichd.org/fileadmin/user_upload/Explosive_Ordnance_Guide_for_Ukraine__GICHD_-_Third_edition__v06_WEB.pdf)

### M999 — 155-мм кассетный артиллерийский снаряд

Доступен индексированный фрагмент первичного Portfolio Book; полный PDF в текущем сеансе не открылся. Это атрибуция конкретного XM1208, не паспорт всех изделий с названием M999.

- [U.S. Army JPEO A&A — Portfolio Book 2025, CAS-24: XM1208 (Israeli M999), доступный индексированный фрагмент](https://www.cpeae.army.mil/Portals/94/Documents/JPEOAAPortfolioBook_2025.pdf)

## Проверка комплекта

1287 карточек, 53 страны, 39 категорий, 987 записей изображений. Все 910 файлов основного изображения сохранены. Сверены 14 страниц PDF, 10 изображений оригинальных таблиц ORD 696(B) и два доступных текстовых источника. Для All Hands проверена публичная текстовая копия, для Portfolio Book — индексированный первичный фрагмент; полные PDF этих двух публикаций не заявлены как прочитанные.

Изменены только текст и добавленные источники перечисленных карточек. Прежние источники, поля, изображения и другие карточки сохранены. Проверены соответствие JSON и SQLite, integrity_check, foreign_key_check, версия содержимого, повторное применение обновления и повторный запуск без изменений. APK не собирался.
