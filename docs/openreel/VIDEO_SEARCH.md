# Astel: поиск видео по теме

27 октября 2026. Локальная версия в OpenReel Astel, рядом с Voicebox.

## Как пользоваться

Открыть **OpenReel Astel → проект → AI Generate → Найти видео**.

1. Ввести тему на русском или английском.
2. Выбрать лимит до 10, 25, 50 или 100 результатов и сортировку; нажать **Найти видео**.
3. Просматривать превью, названия, каналы, длительность и доступное число просмотров. Нажатие на ролик открывает YouTube в обычном браузере.
4. Отметить **В подборку** у подходящих результатов. Вкладка **Подборка** объединяет выбор из разных запросов.
5. **Копировать ссылки** или **Сохранить ссылки** выгружает выбранные URL. Подборка также сохраняется локально между открытиями приложения.

Фильтр длительности применяется к уже полученной выдаче: до 4 минут, 4–20 минут, от 20 минут. Он не увеличивает число результатов и исключает неизвестную длительность. Поиск ограничен YouTube. Выдача может содержать меньше выбранного лимита; повторы и записи без корректного video ID исключаются. Числа просмотров и порядок приходят от YouTube; это не проверка достоверности ролика или рейтинга качества.

За эту функцию не подключены подписки или платные API. Нужен интернет; запрос и запросы миниатюр отправляются YouTube/Google. Вход в аккаунт и cookies не используются. Сами видео эта панель не скачивает: результат текущего этапа — подборка ссылок. Загрузка разрешённого материала, монтаж и передача в Lazy Distribution требуют следующей отдельной интеграции.

## Устройство

```text
OpenReel Astel / AI Generate / Найти видео
  → typed Electron IPC (query, count, order, request UUID)
  → isolated Python + pinned yt-dlp (flat metadata search, download=False)
  → normalized YouTube IDs / canonical watch URLs / thumbnails
  → previews + local selection + TXT links
```

Main запускает только фиксированный локальный Python/module; запрос передаётся JSON через stdin без shell. Renderer не задаёт executable, пути, cookies или произвольный URL. Отмена привязана к окну и UUID, закрытие панели останавливает запрос. На окно допускается один поиск; deadline 60 секунд, ограничение ответа 1 MB. Backend limit 100; подборка ограничена 500 уникальными ссылками. Пустой ответ и ошибка отображаются отдельно.

Поиск кешируется на 5 минут в owner-only `~/.local/share/astel-video-search/cache`, максимум 200 файлов. Runtime находится в отдельном venv и не изменяет зависимости Voicebox. Выбор и последний запрос хранятся в localStorage приложения (`astel.videoSearch.v1`); последний запрос и найденные результаты общие для проектов этого локального приложения. При повреждённом localStorage интерфейс открывается с пустым состоянием.

## Исходники и воспроизводимая установка

- `src/video_editor/video_search.py`: metadata backend и нормализация.
- `scripts/setup_video_search_mac.py`: отдельный runtime, pinned wheel + SHA-256.
- `integration/video-search/0001-openreel-voicebox-and-search.patch`: полный cumulative patch поверх OpenReel `c9340465e5d37e684cc25bdbe746c4ccd45e165c`, включающий принятый Voicebox и поиск. Применять вместо standalone speech patch, не поверх него.
- Старый `integration/voicebox/patches/0002-openreel-local-speech.patch` сохранён. `vendor/openreel` остаётся чистым.

Для существующего Mac с настроенными Voicebox и approved RU/EN bindings:

```bash
~/.local/share/astel-voicebox/venv/bin/python scripts/install_openreel_voicebox_mac.py \
  --with-video-search \
  --node /absolute/path/to/node \
  --pnpm /absolute/path/to/pnpm
```

Нужны Apple Silicon macOS, Python 3.11+, Node 22+, pnpm, FFmpeg и оригинальное `/Applications/OpenReel.app`. Для первой настройки Voicebox см. [локальную озвучку](../voicebox/OPENREEL_LOCAL_SPEECH.md). Установщик не перезаписывает существующий кандидат: перед обновлением закрыть приложение и переместить старый bundle в резервную папку. Проекты живут отдельно в `~/Library/Application Support/OpenReel Astel`. `--built-source` допустим только для уже собранного clone с соответствующим полным patch.

Зависимость [yt-dlp](https://github.com/yt-dlp/yt-dlp#usage-and-options) закреплена на 2026.10.26 из [официального PyPI](https://pypi.org/project/yt-dlp/2026.10.26/). Поиск релевантности использует `ytsearchN:`, поиск по дате — фиксированный YouTube results URL с upload-date/video-only filter. Устаревший `ytsearchdateN:` в этой версии отсутствует. YouTube может менять выдачу/ограничивать запросы; автоматический платный fallback не предусмотрен.

MIT notices OpenReel и Voicebox сохранены. License yt-dlp сохраняется отдельно в установленном runtime `LICENSE.yt-dlp`; dependency не включена в app.asar. Оригинальный OpenReel, его MCP descriptor, production publishing и ASAP/Kevin не меняются. Кнопка работает локально, новые remote MCP tools не добавлены.

## Проверка

См. [машиночитаемый результат](VIDEO_SEARCH_VALIDATION_2026-10-27.json). Typecheck, renderer/main builds, backend/IPC/UI tests и реальный поиск проверяются отдельно от слухового качества Voicebox и video export. Подборка ссылок не меняет таймлайн.
