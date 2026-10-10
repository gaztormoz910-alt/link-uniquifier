# Контекст проекта Link Uniquifier (Facet)

## Описание проекта
Тотальная уникализация ссылок для email-рассылок. Из одной ссылки делает сотни уникальных с рандом-хвостами, обёртками через Google-домены, и множеством техник рандомизации.

## Файлы проекта
- `main.py` (~1000 строк) — бэкенд: генерация уникальных ссылок, обёртки, 12 техник, 248 параметров, облачный HTML, `randomization_strength()`, режим «как есть» (`custom_tail`)
- `gui.py` (~760 строк) — GUI на customtkinter, тёмная тема «slate» (графит `#0d1117` + СИНИЙ акцент `#4f8cff`; визуал намеренно другой, не чёрно-зелёный). Страница ПРОКРУЧИВАЕМАЯ (`CTkScrollableFrame`) — контент не ужимается при уменьшении окна, а скроллится. Тултипов НЕТ, «маркировок» (дисклеймер/статус-баннеры/подписи) НЕТ — одна строка статуса. Плейсхолдеры расписаны с примерами. Дефолт — безопасный (сила ~72%, растёт по мере заполнения до 100%). Опасные техники не выведены. Вставка Ctrl+V/C/X/A при любой раскладке (по keycode). 2 режима (ready/spintax), один счётчик
- `test_fixes.py` — регресс-харнесс (33 гейта G1–G34, номера G8 нет; все зелёные). G7: набор обёрток растёт (в коде их больше, чем в списке ниже — источник истины `main.BRAND_WRAPPERS`), поэтому тест НЕ хардкодит число — инвариант «>=4 + translate удалён», внешние хосты цепочки выводятся из самих билдеров. G33 — гибридный UI-редизайн, G34 — иконки-глифы у секций/кнопок + нормальные стрелки пагинации (◀◀ ◀ ▶ ▶▶)

## Архитектура

### Обёртки (все без подтверждения, direct), базовый набор:
1. `google_amp` — `*.cdn.ampproject.org` (client-side редирект на origin, AMP Cache отключён 01.07.2026)
2. `doubleclick` — `adclick.g.doubleclick.net/pcs/click?adurl=` (302 редирект)
3. `googleads_doubleclick` — `googleads.g.doubleclick.net/pcs/click?adurl=` (302 редирект)
4. `pagead2` — `pagead2.googlesyndication.com/pcs/click?adurl=` (302 редирект)
5. `ad_doubleclick` — `ad.doubleclick.net/pcs/click?adurl=` (302 редирект)
6. `tradedesk` — `insight.adsrvr.org/track/clk?r=` (302 редирект, The Trade Desk)

`google_translate` (translate.goog) УДАЛЁН — для многих сайтов (YouTube и др.) отдаёт пустую страницу и тяжело флагается вендорами.

**Правило многослойности:** Внутренний слой — любая обёртка. Внешние слои — ТОЛЬКО 302-редиректы (doubleclick, googleads, pagead2). Прокси на прокси = 404.

### 12 техник уникализации:
- Рандомные GET-параметры (200+ ключей из пула)
- Якорь (#fragment)
- Case mix (регистр имён параметров)
- Encoding (percent-encoding значений)
- Trailing slash
- Shuffle (перемешивание порядка параметров)
- Обёртки (Google-домены и рекламные редиректоры)
- Поддомены (ОПАСНО — отключено по умолчанию)
- Fake path (ОПАСНО — отключено по умолчанию)
- Dot segments (ОПАСНО — отключено по умолчанию)
- Percent random (ОПАСНО — отключено по умолчанию)
- Протокол http/s (ОПАСНО — отключено по умолчанию)

### 6 пресетов:
soft, medium, aggressive, brand, stealth, paranoid

### Опасные техники (отключены во ВСЕХ пресетах):
- `use_subdomain` — добавляет рандомный поддомен (DNS fail)
- `use_fake_path` — добавляет рандомный путь (404)
- `use_dot_segments` — добавляет `/../` (может 404)
- `use_percent_random` — кодирует буквы в пути (может 404)
- `use_proto_random` — переключает http/https (может не работать)

## Критические правила кодирования

1. **DoubleClick wrappers MUST URL-encode target:** `urllib.parse.quote(target_url, safe='')` — иначе `&` в target разрывает wrapper URL
2. **AMP/Translate домен: дефисы удваиваются ДО замены точек:** `domain.replace("-", "--").replace(".", "-")`
3. **Якорь: ДОБАВЛЯТЬ к существующему, НЕ ЗАМЕНЯТЬ** — для SPA (#/login)
4. **URL fragment (parsed.fragment) должен сохраняться** при реконструкции URL
5. **Cloud HTML: HTML-escape и JSON.dumps для URL** — предотвращает XSS. `generate_cloud_html`: ТРОЙНОЙ редирект (JS `location.replace` + `<meta refresh>` + `<noscript>`-ссылка), срез реферера (`<meta name=referrer no-referrer>`), уникальность каждой страницы (nonce + случайный заголовок + невидимый мусор). Это самый надёжный «свой» враппер — домен облака твой, без подтверждений (гейт G27). Гейт G6 бережёт XSS-экранирование при любых правках шаблона
6. **parse_qsl вместо parse_qs** — сохраняет оригинальное кодирование параметров
7. **Windows: UTF-8 wrapping** для stdout/stderr (cp1252 по умолчанию)
8. **RNG — некриптографический `random.Random()` (Mersenne), НЕ `secrets.SystemRandom`**. Крипто-стойкость для уникализации не нужна, а `SystemRandom`+`secrets.token_hex` дёргали `os.urandom` на каждую операцию и были главным тормозом (профиль: 2.8M вызовов `nt.urandom` на 2000 ссылок). Быстрый hex — helper `_htok(nbytes)` (одно `getrandbits`, ровно 2n hex-символов). Замер: 150 параметров/2 слоя 594→1388 ссылок/с (×2.3), дефолт 4340→6834/с (×1.6). Гейт G30. Скорость/память ∝ (число параметров × число ссылок): при 150 параметрах ссылка ~2475 симв. и 50k = ~125 МБ (2M было бы ~5 ГБ)
9. **Без метаданных.** В проекте нет личных данных, путей машины, имён аккаунтов, следов инструментов и дат работы. У `Facet.exe` нет ресурса версии (в `Facet.spec` нет `version=`), у установщика не заданы издатель/копирайт/URL. Подпись коммитов в этом репозитории — нейтральная (`git config --local`). Служебные каталоги инструментов игнорируются через `.git/info/exclude`, а не через `.gitignore`. `__pycache__` не хранить (в .pyc вшит абсолютный путь)
10. **Собранные бинарники — без дат сборки.** После PyInstaller и после ISCC гоняется `tools/scrub_metadata.py`: обнуляет PE-таймстемпы (`FILE_HEADER.TimeDateStamp` + каталоги debug/export/resource) к синтетической дате 1980-01-01, пересчитывает PE-checksum, нормализует времена файлов и даты членов `.zip`. Иначе exe выдаёт момент и машину сборки. **exiftool для EXE/DLL/ICO/ZIP только ЧИТАЕТ** (писать/удалять не умеет — см. exiftool.org), поэтому чистка идёт через `pefile` (транзитивная зависимость PyInstaller), а не через exiftool. Строки вендоров в сторонних `.dll`/`.pyd` (Python, OpenSSL, Tcl) НЕ трогаем — они не наши и их удаление рискованно. Rich header и debug-каталог целиком тоже оставлены (правка заголовка = тамперинг, лишнее внимание SmartScreen без подписи)

## Отвергнутые обёртки (НЕ работают, НЕ добавлять):

### Массовый тест (41 кандидат):
Протестированы полные цепочки редиректов с follow_chain. НИ ОДИН не прошёл.

**Google-экосистема:**
- google_translate (translate.goog) — удалён: пустая страница на многих сайтах, флагается вендорами
- google_amp_viewer (google.com/amp/s/) — 302 → google.com/url = ПОДТВЕРЖДЕНИЕ
- google_colab (corgiredirector) — 301 → google.com/url = ПОДТВЕРЖДЕНИЕ
- google_weblight — 404
- google_news_redirect (news.url.google.com) — 404
- google_feedproxy — 404
- google_ads_redirect (googleadservices.com/pagead/aclk) — 400
- googlesyndication_simgad — 404
- google_devsite (developers.google.com/devconsole) — 404
- google_maps_redirect — 302 → maps (НЕ редирект на target)
- doubleclick_pagead (ad.doubleclick.net/ddm/trackclk) — 204
- doubleclick_ad2 (ad.doubleclick.net/ddm/clk) — 400

**Microsoft:**
- microsoft_redirect (go.microsoft.com/fwlink) — 302 → bing.com (НЕ target)
- bing_redirect (bing.com/newtabredir) — 302 → bing main page
- office_redirect — 404
- outlook_safelinks — 400
- teams_redirect — 302 → Teams launcher (НЕ target)

**Amazon:**
- amazon_redirect (gp/redirect.html) — 404
- amazon_r (gp/r.html) — 302 → amazon.com main page
- aws_redirect — 404

**Рекламные сети:**
- criteo — DNS fail
- taboola — 404
- outbrain — 500
- tradedoubler — 200 без контента цели
- awin_redirect — 302 → closedMerchant.html
- cj_redirect — 302 → members.cj.com/404
- shareasale — 302 → awin closedMerchant
- impact_redirect (linksynergy.com) — 400

**Другие:**
- DuckDuckGo — нужна сессия
- Google Travel — нужен токен
- Bing — нужен base64 session token
- exit.sc — ведёт на soundcloud
- VK, Twitter, LinkedIn, YouTube, Pinterest — с подтверждением
- adobe — DNS fail
- apple — 302 → apple support (НЕ target)
- spotify — 403
- baidu — SSL timeout
- yandex — 302 → ya.ru (НЕ target)
- naver — 302 → HTTP 418 (bot protection)
- cloudflare_amp — 404
- jsdelivr — 400
- tumblr/href.li — 403
- reddit outbound — 302 → reddit/invalid_token
- anonym.to — 502
- dereferer.me — timeout
- nullrefer.com — промежуточная JS-страница (/lander), НЕ прямой редирект
- rebrandly — 403
- zapier — 404

## GUI
- customtkinter 5.2.2
- Стиль: нейтральная тёмная база + синий акцент (гейт G33). Палитра: фон `#0b0d12`, шапка `#0f1116`, карточки `#15171d`, приподнятые `#1a1d24`, поля `#0e1015`, границы `#262a33`/`#323744` (`COLOR_BORDER`/`COLOR_BORDER2`), текст `#e6e8ec`, dim `#8b90a0`/`#5b606e`, warn `#fbbf24`, error `#f87171`, info `#38bdf8`. Акцент — СИНИЙ `#4f8cff` (hover `#3b74e6`, soft-поверхность `#16233c`): зелёный `#4ade80` ЗАПРЕЩЁН (G25 — визуал не чёрно-зелёный). Шрифт Segoe UI / Consolas. Фиксированная **шапка-хром** (`self.header`, не скроллится) — бренд-чип (`brand_chip`, глиф ⬡ на accent-soft) + двухцветный вордмарк LINK/UNIQUIFIER + mono-подзаголовок + живой индикатор справа (`bridge_label`, состояние по цвету статуса через `_set_status`) + разделитель. Карточки-секции (`_panel(title, sub=None, icon=None)`): вертикальный акцентный «таб» слева + опц. иконка-глиф (в акценте) + заголовок + опц. mono-подпись `.sub`. Иконки секций (G34): 🔗 Ссылка, 🏷 Свои параметры, ⚙ Настройки, 📋 Результат — в шрифте Segoe UI рендерятся МОНОХРОМНЫМ глифом в акцентном цвете (не пёстрым эмодзи). Кнопки с глифами: ⚡ Сгенерировать (■ СТОП), ⧉ Копировать, ⭳ Сохранить, ☁ Cloud HTML, ↺ Сброс. Сегменты — пилюли-табы. Прогресс-бар тонкий rounded, статус силы — mono. Пагинация (G34): стрелки `◀◀ ◀ ▶ ▶▶`. ВЕСЬ функционал/бэкенд не тронут — доказано всеми прочими гейтами
- Два режима: ready (N уникальных) и spintax ({url1|url2|...}). ОДИН счётчик `count_entry` на оба режима (для spintax кламп до `MAX_SPINTAX`)
- ПРОКРУЧИВАЕМАЯ страница: всё внутри `self.scroll` (`CTkScrollableFrame`). Контент НЕ ужимается при уменьшении окна — страница скроллится (гейт G14). Результат `result_box` — ФИКС-высоты (`RESULT_HEIGHT=380`, `wrap="none"`) со своим скроллом; колесо над ним изолировано (`_result_wheel` → return "break"), крутит только его, не страницу. ГОРИЗОНТАЛЬ тачпадом/Shift+колесом: `<Shift-MouseWheel>` (путь Windows) → `_result_wheel_x` двигает `xview` и тоже гасит всплытие; X11-жест Button-6/7 повешен опционально в try/except (на Windows Tk такого события нет — bind падал бы). Гейт G28. Окно `1180x860`, minsize `760x560`
- Секции (`_panel`): «Ссылка», «Свои параметры и макросы», «Настройки уникализации» (`settings_section`, `wrapper_menu`, `layers_menu`, `params_min_entry`, `params_max_entry`, `domains_entry`), «Результат». Тумблера «Дополнительно» нет
- Кнопка «Сброс» (`btn_reset`→`_reset_defaults`): дефолт random/1/5–8/пусто. Кнопка генерации `btn_generate`: «СГЕНЕРИРОВАТЬ»↔«СТОП» (`_cancel_generation`)
- Сила рандомизации (`randomization_strength`) двухслойная: БАЗА (безопасные внутренние техники, макс 30) + РЫЧАГИ ИНТЕРФЕЙСА (параметры до 22, обёртка+слои до 28, домены до 12, свои +8, макс 70). Чем больше заполнил — тем выше. Дефолт ~72% (с запасом), всё заполнено = 100%. Пороги: ≥70 ВЫСОКАЯ, ≥40 СРЕДНЯЯ. Цвет бара/метки по порогам
- Дефолт: `SAFE_TECHNIQUES` (безопасные ВКЛ, опасные ВЫКЛ), 1 слой, обёртка random, 5–8 параметров
- ТУЛТИПОВ НЕТ (убраны намеренно — нет класса `Tooltip`, нет `_tip`/`_tooltips`)
- «МАРКИРОВОК» НЕТ (убраны намеренно): нет жёлтого дисклеймера-футера, нет статус-баннеров «✅ готово», нет `count_label`/`warn_label`/`mode_hint`/`page_hint`/`danger note`. Осталась ОДНА компактная строка статуса `status_label` (прогресс/итог/ошибки, `_set_status`), плейсхолдеры расписаны с примерами. Поле своих параметров: плейсхолдер МЕНЯЕТСЯ под режим сегмента (`custom_mode_var.trace_add` → `_on_custom_mode_changed`): `CUSTOM_PH_THROUGH` («через &» — список через запятую, каждый пункт = отдельный `?параметр`) / `CUSTOM_PH_ASIS` («как есть» — дословный хвост в конец, для #-фрагментов). Гейт G29
- Фикс раскладки: `clipboard_intent()` + `bind_all("<Control-KeyPress>")` — вставка по keycode
- Клик мимо инпута снимает фокус: `wants_defocus()` + `bind_all("<Button-1>")` → `focus_set()`
- Лимит 10к снят: `clamp_count()` до `MAX_LINKS=2_000_000` (весь набор в памяти в `self.links`)
- Пагинация: `page_bounds()` + `_render_page()` — в текстбоксе ТОЛЬКО одна страница (`PAGE_SIZE=1000`). `page_bar` пакуется под результатом (`_set_pagination_visible`), спинтакс прячет. Кнопки ◀◀ ◀ ▶ ▶▶ + переход по номеру. Копирование/сохранение (`_all_text()`) берут ВЕСЬ набор
- Производительность/лаги (2 пути, выбор по объёму в `_start_generation`):
  - **Крупный объём (`count >= _MP_THRESHOLD=5000`) → ОТДЕЛЬНЫЙ ПРОЦЕСС** (`main.generate_worker` через `multiprocessing.Process`, гейт G32). Почему процесс, а НЕ поток: у потока Python-код держит GIL и душит UI-цикл Tk (окно лагало при скролле во время генерации — раньше поток и убрали). Процесс GIL не делит → UI-поток свободен. Замер (15k, 15–40 парам, 2 слоя): UI-поток занят **87% времени (поток) → 0–3% (процесс)**, throughput сопоставим (~2500 ссылок/с). Воркер шлёт ссылки батчами (`_GEN_BATCH=2000`) в `mp.Queue`; UI дёшево переливает их в `_mp_drain` (каждые `_MP_POLL_MS=30`мс), считает прогресс, финиш по маркеру `("__done__", attempts)`. «СТОП» = `mp.Event().set()`; закрытие окна = `destroy()`→`_kill_worker()` (нет зомби). Дедуп в воркере (`hash`). Параметры из `_gather_params` picklable. `mp.freeze_support()` в `__main__`. Windows: `after`-таймер квантует по ~15.6мс, поэтому мельче дробить кадры БЕСПОЛЕЗНО (замерено: бюджет 8/4мс только хуже) — настоящий фикс это процесс.
  - **Мелкий объём / фолбэк → кооперативно КАДРАМИ** (`_start_generation_inproc`→`_gen_step`, бюджет `_GEN_FRAME_BUDGET=0.018`, дедлайн раз в 64 итерации, гейт G23/G24). Мелкие завершаются мгновенно — лагать нечему, а ~0.5с на старт процесса не нужны.
  - Спинтакс в обоих путях: N ready-вариантов → `"{" + "|".join + "}"`. `self._generating`/`self._mp` — состояние.
- Запуск через `main()` (не голый `app.mainloop()`): `KeyboardInterrupt` (Ctrl+C в терминале) гасится и окно закрывается — это НЕ краш. ДВА пути Ctrl+C: (1) прямо в mainloop → ловит `except KeyboardInterrupt` в `main()`; (2) ВНУТРИ after-колбэка Tk (напр. периодический трекер темы customtkinter — именно он давал «Exception in Tkinter callback») → перехватывает override `report_callback_exception` на корне: на `KeyboardInterrupt/SystemExit` тихо `quit()` + флаг `_interrupted` (main() печатает «Закрыто»), прочие исключения печатает как обычно, чтобы не прятать баги. Гейт G31. Раньше Ctrl+C вываливал простыню трейсбека, а сдвинутые номера строк в ней (если файл правился на ходу) вводили в заблуждение

## Окружение
- Windows, Python 3.13
- PowerShell
- `grep` недоступен — использовать `Select-String` или `findstr`

## Запуск
```
python gui.py      # GUI
python main.py     # CLI примеры
```

## Сборка и релиз (Windows-установщик «Facet»)
Проект пакуется в `Facet-setup.exe` (без Python у пользователя). Имя продукта — **Facet** (заголовок окна `Facet <версия>`, вордмарк «FACET»).
- **Иконка**: мастер `assets/Facet.png` → `assets/Facet.ico` (10 размеров 16..256) через `tools/make_icon.py` (уменьшение в ЛИНЕЙНОМ свете + резкость с возвратом энергии). В окно ставится по нативным размерам через WinAPI (`_apply_native_icons`), классу окна (`iconbitmap(default=)`), плюс `SetCurrentProcessExplicitAppUserModelID("Facet.App")`. PNG-мастер и кадры .ico — только критичные чанки (IHDR/IDAT/IEND), без текстовых/EXIF-блоков.
- **Версия — один источник**: файл `VERSION`; `tools/set_version.py X.Y.Z` пишет его; читают все — окно (`app_version()`), `.iss`, CI. Ресурса версии у `.exe` НЕТ намеренно (свойства файла — метаданные). `resource_path()` — доступ к ресурсам и из исходников, и из `sys._MEIPASS`.
- **Сборка**: `Facet.spec` (PyInstaller onedir, `collect_all('customtkinter')`, `numpy` в excludes — приложение его не использует, без `version=`). `requirements.txt` = customtkinter + **Pillow** (customtkinter импортирует PIL, но НЕ объявляет его в зависимостях). `freeze_support()` первым в `__main__` — критично для multiprocessing в frozen-exe.
- **Установщик**: `Facet.iss` (Inno Setup) — в `{localappdata}\Programs\Facet`, `PrivilegesRequired=lowest` (без UAC), `OutputBaseFilename=Facet-setup` (БЕЗ версии — иначе постоянная ссылка ломается). AppId фиксирован. Издатель/копирайт/URL не задаются. В CI сам Inno Setup ставится ПРЯМОЙ загрузкой закреплённого `innosetup-6.7.3.exe` с GitHub-релиза jrsoftware + сверка SHA256 и тихая установка (`choco install innosetup` протухал по хешу после выхода новой версии Inno и ломал шаг «Собрать установщик» — URL релиза неизменяемый; choco оставлен запасным путём).
- **Чистка метаданных сборки**: `tools/scrub_metadata.py <dir>` / `--file <pe>` / `--verify` — обнуляет PE-таймстемпы и времена файлов (см. п.10 «Критических правил»). Локально: `python tools/scrub_metadata.py dist/Facet` после сборки.
- **CI**: `.github/workflows/release.yml` — на тег `v*`: собирает exe → `scrub_metadata.py dist/Facet` → смоук (`--selftest` по УЖЕ вычищенному exe, доказывает, что правка PE не сломала запуск; + запуск окна) → собирает установщик → `scrub_metadata.py --file` по setup.exe → `--verify` обоих → публикует релиз. Порядок важен: чистим ДО смоука и ДО упаковки. Выпуск новой версии: `git tag vX.Y.Z && git push origin vX.Y.Z`.
- **Постоянная ссылка**: `<репозиторий на GitHub>/releases/latest/download/Facet-setup.exe`.
- **Проверки** (`tools/verify_icon.py`, `verify_version.py`): кадры .ico = мастер (+ негативный контроль); версия сходится (VERSION == окно), ресурса версии у exe нет (+ негативный контроль детектора).
- **Режим `--selftest <лог>`**: headless-прогон генерации (окна нет, `console=False` → пишет в файл), код 0/1.
