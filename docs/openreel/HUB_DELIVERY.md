# OpenReel → Canvas → существующий Hub

Проверка 28 октября 2026, ветка `integration/astel-media-canvas-stack`.

Установлены локальная форма передачи **тестового черновика**, постоянный журнал запросов, восстановление прежнего Drive-входа и чтение реальной очереди Hub. Сквозная передача MP4 пока не подтверждена: существующий `drive-work` refresh token истёк; повторный вход Google требует действия владельца. Первый запрос остановился до создания папки, MP4 и плана Hub. Публикация не включалась.

## Использование на Mac

1. OpenReel Astel → AI Generate → Материалы и истории → Для Canvas → **Открыть Canvas на Mac**. Открывается `http://127.0.0.1:17531/`. Кнопка проверена в установленном приложении.
2. В «Черновиках с Mac» выбрать точную версию ролика. Указать существующий Instagram-аккаунт, подпись и время тестового слота. **Передать тестовый черновик в Hub** ставит durable задание; режим принудительно `simulation`.
3. При ошибке Drive нажать **Повторно войти в Google Drive**, затем появившуюся ссылку. Используется прежний локальный Google OAuth client и тот же scope `drive.file`, без новых ключей. Завершить вход в Google самостоятельно; предупреждение о непроверенном тестовом приложении агент не обходит. Вход живёт десять минут; после истечения кнопку можно нажать заново.
4. После входа — **Продолжить передачу** у существующего задания. Не создавать новый запрос ради повтора. Сначала загружается приватная копия окончательного MP4 в отдельную app-owned папку **Astel Video Delivery**. Исходная папка материалов и destination ASAP не меняются.
5. После удалённого hash/size/type readback выполняются Hub `preview → submit → status`. Успех показывается только после совпадения plan ID, input digest и режима `simulation`, без approval, attempts или receipt. Это Hub `DRAFT`; приватный файл ещё недоступен анонимному серверному исполнителю.
6. При необходимости владелец отдельно отмечает согласие и нажимает **Разрешить чтение этой копии MP4**. Доступ получает любой обладатель ссылки, включая сервер Hub; открывается только проверенный финальный MP4 с синтезированным голосом, `reader`, `allowFileDiscovery=false`. Папка, RAW и записи голоса не открываются. Эта операция не была выполнена агентом на реальном файле. Статус означает проверенное разрешение Drive, а не завершённую загрузку файла самим сервером Hub.
7. **Очередь Hub** читает реальные inbox/status/metrics существующего проекта `copilot`. Проверены пять уже существующих заданий; эти задания интеграция не меняла. Согласование публикации остаётся в действующем защищённом канале владельца. Здесь нет approve/review/schedule/publish/cancel маршрутов.

После изменения сценария или MP4 требуется новая версия истории. Изменение подписи, аккаунта или времени создаёт новую delivery revision при сохранении source story revision. Локальное «Принять черновик» является редакторским решением; оно не одобряет публикацию.

## Реализация

- `hub_delivery.py`: фиксированный существующий Hub origin, allowlist действий, только `copilot` и `simulation`. Операторский credential используется для preview/submit; отдельный status-only credential — для UI чтения. Даже если исходный credential имеет более широкие scopes, adapter не вызывает исполнительные действия.
- `drive_delivery.py`: прежний `drive-work` grant, проверка аккаунта, отдельная приватная папка, заранее зарезервированные file IDs, resumable chunks, удалённый SHA-256/MD5 readback. Сохранённая upload session приватна и удаляется после readback. Повтор не создаёт новую копию. Ошибку доступа нельзя обойти переключением на другой аккаунт/папку.
- `drive_authorization.py`: запускает существующий OAuth helper в отдельном процессе. В UI возвращается только локальный `/authorize` entry URL. Google callback, auth code, токены и секрет клиента не попадают в Canvas. Зависимость: прежний `~/Projects/asap-gta6-pipeline/src/video_editor/asap/google.py` и установленный Voicebox Python.
- SQLite `hub_handoffs`: журнал binding `story + digest + MP4 hash + delivery revision + immutable input + deterministic plan ID`. Потеря submit reply сначала сверяется через status. Семантически одинаковый запрос с другим UUID также использует существующий binding. Уже отправленный запрос можно сверить после истечения тестового слота; новая отправка требует будущего времени.
- Local Canvas: прежний приватный HTML не переписывается. Проверяемые hooks адаптируются при выдаче; Hub reader работает через фиксированные private backend endpoints. Токены остаются вне renderer. Cookie/Host/Origin/CSRF граница действует и на новые действия.
- Просмотр Hub MP4 может использовать точную локальную копию по SHA-256 с явной подписью. Такое превью не доказывает доступ сервера к Drive. После выключения Mac оно недоступно.

`availableUntil` — обещание сохранить копию минимум до указанного срока (тестовый слот + семь дней), не автоматически исполняемый TTL. Архивация/retention и серверное media preflight ещё требуют отдельной проверки. Права Drive можно отозвать вручную; сервер должен повторять media preflight перед реальной доставкой.

## Проверки и границы

Python: **110 passed** в проверках workspace, Canvas, Hub/Drive, Voicebox, story jobs/pilot, discovery и OpenReel. Проверены потеря финального upload reply, потеря submit reply, повтор без дубликата, caption revision, stale digest, запрет live и исполнительных действий, точное согласие на file sharing, read-only HTTP proxy, CSRF и ограниченный loopback OAuth URL. Включены проверки против существующего JS-контракта Hub. Web typecheck/build, JS syntax и signed bundle verification прошли; прежние предупреждения upstream о browsers data/WASM/chunks остались.

Реальный UI подтвердил чтение очереди и возврат того же failed handoff к конкретной ошибке Drive. Это не доказательство успешного реального upload/submit. Нет owner approval, scheduling, публикации, новых платных сервисов, production deployment или изменения publishing configuration.

Следующий обязательный acceptance после входа: тот же MP4 → Drive metadata hash → simulation DRAFT readback → та же карточка в реальной очереди → отдельное согласие владельца на доступ к копии → анонимный download/preflight и совпадение bytes. Согласование/live dispatch не являются частью этого acceptance. Windows/Kevin остаётся Stage 2.

## Setup / rollback

Повторно выполнить существующий `scripts/setup_media_workspace_mac.py --node /absolute/path/to/node --start-canvas`; он сохраняет private HTML/ZIP, SQLite и медиа, но отказывает во время активного worker. Существующие private credentials читаются из `~/.config/astel-distribution/`; их значения в repo/HTML/чат не копируются. На чистом Mac сначала требуется штатное подключение действующего Hub и Google client; этот installer не выпускает credentials и не меняет production.

Установлено `~/Applications/OpenReel Astel.app`; предыдущая версия сохранена в `~/.local/share/astel-openreel-voicebox/builds/before-hub-20261028/OpenReel Astel.app`. Cumulative patch и upstream MIT notices включены в сборку. `/Applications/OpenReel.app`, принятый Amazon-пилот и `main` сохранены.

Основания для Drive реализации: [resumable uploads](https://developers.google.com/workspace/drive/api/guides/manage-uploads), [предварительные file IDs](https://developers.google.com/workspace/drive/api/guides/create-file), [поля checksum](https://developers.google.com/workspace/drive/api/reference/rest/v3/files), [права доступа](https://developers.google.com/workspace/drive/api/guides/manage-sharing). Hub contract проверен по существующему локальному исходному коду и текущему authenticated READ.
