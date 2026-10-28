# OpenReel Astel: вставить текст → получить свой голос

27 октября 2026 · ветка `integration/voicebox-local-first`.

Реализован и установлен отдельный кандидат `~/Applications/OpenReel Astel.app`. Обычный `/Applications/OpenReel.app`, его проекты, MCP descriptor, publishing и ASAP не заменяются.

## Пользовательский сценарий

1. Открыть OpenReel Astel, создать проект или открыть Recent → Vertical (тестовый проект).
2. Слева **AI Generate → Text to Speech → Voicebox · мой голос**.
3. Выбрать **Олег — русский** или **Oleh — English**, вставить текст и нажать **Озвучить**.
4. Прослушать в панели. **Скачать WAV** сохраняет файл; **Добавить на таймлайн** создаёт аудиодорожку и ставит клип после существующего материала. Клип можно передвинуть обычными средствами редактора.

Русский по умолчанию: 100%, тёплый звук B. Английский: собственный английский reference, 102%, без русского EQ. Настройка темпа не меняет произношение. Скрипт не переписывается. Лимит — 5000 символов.

Один активный запрос из панели за раз. Можно переключить вкладку или перезапустить редактор: известный ID восстанавливается без новой генерации. Все результаты сохраняются на диске, даже когда панель показывает уже следующий запрос. При сбое IPC «Повторить подключение» использует тот же ID и точный запрос. Изменённый запрос с прежним ID отклоняется.

Первый запрос сам запускает локальный Voicebox. Терминал для повседневной работы не нужен. LaunchAgent не устанавливается; служба продолжает работать в фоне и держит модель в памяти после генерации. В тестах 6,16 с русской речи потребовали около 50 с; 7,616 с английской речи с запуском службы — около 85 с. Это измерения коротких проб на текущем Mac, а не гарантия скорости для длинного текста.

## Как устроено

```text
OpenReel Text to Speech / Voicebox
  → typed Electron IPC (approved profile alias + text + job UUID)
  → local Python coordinator + persistent job folder
  → pinned Voicebox REST on 127.0.0.1:17493
  → Qwen Base 0.6B + approved personal reference
  → immutable raw WAV → FFmpeg reviewed tone/tempo → hashed PCM WAV
  → audio preview / download / OpenReel media library + audio timeline
```

Renderer не получает private profile bindings или пути reference и не передаёт произвольные файловые пути/команды. Python вызывается фиксированным executable, JSON идёт через stdin, shell не используется. Main читает только проверенный job WAV, проверяет realpath и SHA-256. Loopback runtime проверяется по Astel marker и точным reference/transcript/model receipts. Общего голоса при ошибке нет.

Фоновая задача хранится в `~/.local/share/astel-voicebox/openreel/jobs/<uuid>/`: `job.json`, snapshot binding, `raw/manifest.json`, исходный `raw/narration.wav`, обработанный `narration.wav`, private log. Текст, голосовые reference и WAV в Git не добавляются. Для идентификации текста используется неизменяемый запрос с fingerprint; для готового WAV — SHA-256.

Отмена сохраняется флагом и отправляется upstream один раз. Активный модельный шаг может завершиться перед остановкой. При неопределённом результате POST без generation ID повторный POST автоматически не выполняется: задача останавливается для проверки истории.

Импорт использует существующий OpenReel media decoder/storage. Track/clip строятся на копии проекта с отдельной undo history; перед применением проверяются ID и неизменность открытого проекта. При смене проекта/ручном изменении черновик не перезаписывает новый state. Успешное добавление входит в одну undo group. Повторное добавление использует тот же media asset.

## Изоляция и исходники

- OpenReel upstream: `c9340465e5d37e684cc25bdbe746c4ccd45e165c`.
- Voicebox upstream и required-clone patch остаются закреплены в `integration/voicebox/upstream.json`.
- `integration/voicebox/patches/0002-openreel-local-speech.patch` содержит UI, preload, main IPC, contracts и тесты. Он применяется только к отдельному clone; `vendor/openreel` остаётся чистым.
- `src/video_editor/voicebox_jobs.py` — persistent job coordinator.
- `scripts/install_openreel_voicebox_mac.py` — воспроизводимая установка bridge и отдельного app bundle.
- App user data: `~/Library/Application Support/OpenReel Astel`.
- Candidate MCP descriptor: `~/.openreel/astel-voicebox-mcp-endpoint.json`. Содержит секрет; не копировать в чат/Git. Оригинальный `~/.openreel/mcp-endpoint.json` не заменяется.
- Кандидат не включает upstream auto-updater, чтобы обновление не стёрло интеграцию.
- MIT license OpenReel и существующие LICENSES включены в bundle; MIT Voicebox сохранена в integration. Оригинальные Electron helpers сохраняют свои имена для корректного запуска macOS; display name и bundle ID кандидата отдельные.

## Установка на Mac

Требуются Apple Silicon, FFmpeg, уже настроенный pinned Voicebox runtime с моделью и approved RU/EN bindings, Node 22+ и pnpm. Для первичной установки самого Voicebox см. [README](README.md). Установщик проверяет bindings через работающий локальный API; перед первой установкой запустить `scripts/start_voicebox_mac.sh`.

Из корня репозитория:

```bash
~/.local/share/astel-voicebox/venv/bin/python scripts/install_openreel_voicebox_mac.py \
  --ru-binding /absolute/path/to/oleh-ru.binding.json \
  --en-binding /absolute/path/to/oleh-en.binding.json \
  --node /absolute/path/to/node \
  --pnpm /absolute/path/to/pnpm
```

Установщик создаёт отдельный clone из полного pinned vendor, применяет patch, устанавливает lockfile, проверяет типы, собирает renderer/main и создаёт отдельный bundle на базе уже установленного `/Applications/OpenReel.app`. Не скачивает новые модели и ничего не публикует. Существующий кандидат не перезаписывается: завершить приложение и сохранить старый bundle под другим именем перед переустановкой. Данные проектов находятся отдельно от bundle.

На текущем Mac готовый clone: `~/.local/share/astel-openreel-voicebox/source-c9340465`. Для проверенного уже собранного clone доступен `--built-source /absolute/path/to/clone`; тогда повторная сборка пропускается. `--bridge-only` обновляет только owner-only Python bridge и проверяет сохранённые bindings. Не менять binding/reference во время активной генерации.

## Проверено

- Python adapter + persistent jobs: **30 passed**, включая idempotency, resume без POST, неопределённую отправку, отмену, WAV/hash/tempo и сохранность source.
- Desktop suite: **141 passed, 7 skipped**. Пропущены upstream integration suites; это не проверка полного video export/Aurora.
- UI и timeline integration + существующий media import: **16 passed**.
- Web/desktop typecheck и production renderer/main build прошли. Остались прежние upstream предупреждения о browser data, optional WASM URLs и размере chunks.
- В установленном app через интерфейс сгенерированы RU 6,16 с и EN 7,616 с; оба WAV проигрываются HTML audio (`readyState=4`, unmuted, без decoder error).
- Проверены переключение панели во время генерации, автоматический запуск остановленной службы, восстановление после перезапуска app без новой генерации, скачивание EN WAV с совпадением SHA-256, обе аудиодорожки и Undo/Redo одной вставки.
- Проверка корректной подписи ad-hoc bundle прошла. Это локальная сборка, не notarized публичный релиз.

Сходство/дикция новых проб требуют пользовательского прослушивания; технический playback не заменяет слуховую оценку владельца. Основа голоса и preset B взяты из ранее принятых личных проб.

## Следующие этапы

Далее — деление сценария на редактируемые блоки, регенерация выбранного фрагмента, тайм-коды и субтитры по конечному обработанному WAV, затем подбор/нарезка видео. Автосборка и publishing этой задачей не реализованы и не включены.

MCP не нужен для кнопки. Существующий ChatGPT connector по-прежнему относится к обычному OpenReel. Для управления кандидатом отдельно выбрать его descriptor в локальном shim, заново выполнить discovery и read открытого проекта; существующий туннель автоматически не перенастраивался. Voicebox generation пока доступна через нативную панель/локальный coordinator, а не через новые remote MCP tools. Kevin/Windows остаётся Stage 2; текущий сценарий полностью выполняется на Mac.
