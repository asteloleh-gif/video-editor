# Voicebox: локальный голосовой пилот

27 октября 2026. Ветка: `integration/voicebox-local-first`.

Первый этап реализован как отдельная локальная служба Voicebox с Astel-адаптером. На Mac установлены зависимости, скачан Qwen3-TTS Base 0.6B, проверены загрузка модели через Metal, REST и настоящий MCP discovery/read. Это **API-служба, а не установленное desktop-приложение с окнами**. Личный профиль Олега ещё не создан; качество речи и сходство не проверены.

## Где запускаем

| Вариант | Решение |
| --- | --- |
| Mac, Apple Silicon, 16 GB | Stage 1: текущий локальный пилот, один голос и одна генерация за раз. |
| Windows / Kevin | Stage 2, только если измеренная скорость или качество на Mac недостаточны. GPU и драйверы Kevin пока не проверялись. |
| Облачный GPU | Возможный последующий исполнитель той же задачи; сейчас не создаётся и не оплачивается. |

Локальность не обязательное ограничение Voicebox: upstream поддерживает remote backend. Для первого голоса Mac удобнее: образец, профиль и результат находятся на одной машине. После скачивания выбранных весов этот Qwen-путь использует локальный checkpoint; Hugging Face включён в offline mode, Voicebox Cloud выключен. Это настройки приложения, а не сетевой firewall всей ОС.

Схема первого этапа: **собственная запись → профиль Oleh EN → утверждённый английский текст → WAV и manifest → прослушивание Олегом**.

Следующий этап после приёмки: WAV → OpenReel или существующий renderer → проверенный MP4 → существующий Distribution Hub. Автопубликация, GTA6 cast и каналы этим пилотом не меняются.

## Что сохранено и изменено

- `vendor/voicebox` — отдельный git submodule upstream, commit `8af7efe62fab8d33e2a5dfbedabaa45f68a5184f`. MIT license сохранена в submodule и `integration/voicebox/LICENSE.voicebox`.
- `integration/voicebox/patches/0001-required-clone.patch` применяется только к отдельной runtime-копии. Upstream submodule не редактируется.
- Qwen MLX требует существующий reference, точный transcript, Base-модель и оба encoder-компонента. Ошибка, несовместимая модель, пустой/нечисловой/полностью тихий результат останавливают генерацию. Генерации без reference в этом пути нет.
- Неподдерживаемый `instruct` завершается ошибкой. Лёгкий естественный акцент проверяем на собственном английском reference, без обещания управлять им одной текстовой командой.
- `src/video_editor/voicebox.py` привязывает один профиль к точному sample/transcript/hash; сохраняет версии WAV, script, request, seed, model identity, audio hash и QA status. Изменение reference выявляется до отправки и при получении результата.
- Повторного HTTP POST при timeout нет. С известным generation ID используется `resume`; без него сначала разбираем историю. Внутри upstream остаются документированные разбиение длинного текста и локальные adaptive retries при нестабильном аудио; seed сам по себе не гарантирует побайтовое воспроизведение.

Изолированный runtime по умолчанию: `~/.local/share/astel-voicebox`. В нём `venv`, pinned source, `data`, `hub`, `models/0.6B`, installed requirements и model receipt. Пути можно перенести целиком через `ASTEL_VOICEBOX_HOME`; старые ASAP окружения не используются. Веса занимают около 2,51 GB и не включаются в Git.

## Запуск на Mac

Из корня этой ветки:

```bash
scripts/setup_voicebox_mac.sh
scripts/start_voicebox_mac.sh
```

Setup требует Python 3.12, использует отдельный venv, устанавливает закреплённые зависимости и скачивает только reviewed 0.6B checkpoint. При необходимости указать Python: `ASTEL_PYTHON=/absolute/path/to/python3.12 scripts/setup_voicebox_mac.sh`. FFmpeg нужен для подготовки reference; на текущем Mac он уже есть.

Во втором терминале:

```bash
scripts/voicebox.sh doctor
```

REST: `http://127.0.0.1:17493`. MCP: `http://127.0.0.1:17493/mcp`. Служба запускается в foreground; остановка — Ctrl+C. Автозагрузка/LaunchAgent не устанавливались. Для повторного запуска после перезагрузки использовать start script. `/health` показывает загруженную модель только после её загрузки; setup сам инференс не запускает.

## Первый личный голос

Записать 30–60 секунд естественной английской речи: один голос, без музыки, без попытки искусственно усиливать акцент. Из записи выбрать чистый фрагмент **10–25 секунд** и записать его дословный transcript. Upstream принимает reference только 2–30 секунд; целую минуту загружать в профиль нельзя.

Ниже имена файлов примера: заменить исходный путь своим. `input/` и `output/` исключены из Git.

```bash
scripts/voicebox.sh prepare-reference \
  --input /absolute/path/oleh-recording.m4a \
  --start 5 --duration 20 --output input/voicebox/oleh-reference.wav

scripts/voicebox.sh register \
  --reference input/voicebox/oleh-reference.wav \
  --transcript input/voicebox/oleh-reference.txt \
  --binding output/voicebox/oleh-en.binding.json

scripts/voicebox.sh generate \
  --binding output/voicebox/oleh-en.binding.json \
  --script input/voicebox/pilot-en.txt \
  --output output/voicebox/pilot-001
```

`prepare-reference` сохраняет RAW и создаёт отдельный mono PCM WAV 24 kHz. Transcript должен соответствовать выбранному фрагменту. Файл `pilot-en.txt` содержит текст для новой озвучки, а не transcript образца.

Результат: `narration.wav`, `script.txt`, `manifest.json` в новом каталоге версии. `qa_status=awaiting_owner_listening` означает, что технически полученный файл ещё не принят как собственный голос.

При незавершённой известной генерации:

```bash
scripts/voicebox.sh resume --output output/voicebox/pilot-001
```

Не переиспользовать существующий output для другой версии. При `registration_incomplete` или `submission_unconfirmed` проверить сохранённый receipt и историю сервера до новой попытки. WAV/M4A от пользователя можно сначала получить из указанной Drive-папки, затем обработать локально; автоматический Drive watcher пока не настроен.

## Проверка качества и следующие MCP steps

1. Принять один reference и exact transcript; создать отдельный `Oleh EN`.
2. Сравнить короткую речь, числа, имена и 45–60 секунд непрерывного текста. Олег оценивает узнаваемость, понятность английского, акцент и отсутствие артефактов. Замерить время **генерации**, не путать его с загрузкой модели.
3. Если результат слабый, сравнить 1.7B Base или Chatterbox на том же тексте/reference. Они сейчас не установлены; 1.7B не включается как скрытый fallback.
4. Локальный MCP уже проверен: четыре инструмента discovery, успешный `voicebox_list_profiles`. MCP ещё не зарегистрирован как доступный этому чату Voicebox connector. Для подключения локального агента использовать Streamable HTTP URL выше; `X-Voicebox-Client-Id` обозначает клиента и не является паролем.
5. Сначала разрешить READ списка профилей. `voicebox_speak` генерирует и воспроизводит через динамики; для монтажных файлов использовать Astel REST adapter. Whisper/dictation и остальные движки этим минимальным окружением не валидировались.
6. Для облачного чата потребуется отдельный защищённый доступ к Mac. Публичный порт не открывать: upstream remote docs прямо указывают отсутствие API authentication. Туннель, VPN и конфигурацию доступа делать отдельным шагом после голосового теста.

Проверки и их границы: [VALIDATION.json](VALIDATION.json). Источники и причины выбора: [RESEARCH.md](RESEARCH.md).
