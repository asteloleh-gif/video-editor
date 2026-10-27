# Voicebox research: local first, 27 October 2026

## Версии и источники

Проверен актуальный GitHub HEAD Voicebox через `git ls-remote` и полный clone, не поисковый snippet: `8af7efe62fab8d33e2a5dfbedabaa45f68a5184f` от 7 октября. Python package в этом source сообщает v0.6.0; номер release binary и source version нельзя смешивать.

Основные первоисточники:

- [Voicebox source и REST/MCP overview](https://github.com/jamiepine/voicebox/tree/8af7efe62fab8d33e2a5dfbedabaa45f68a5184f).
- [MLX backend на проверенном commit](https://github.com/jamiepine/voicebox/blob/8af7efe62fab8d33e2a5dfbedabaa45f68a5184f/backend/backends/mlx_backend.py).
- [Remote mode и отсутствие API authentication](https://github.com/jamiepine/voicebox/blob/8af7efe62fab8d33e2a5dfbedabaa45f68a5184f/docs/content/docs/overview/remote-mode.mdx).
- [MCP server](https://github.com/jamiepine/voicebox/blob/8af7efe62fab8d33e2a5dfbedabaa45f68a5184f/backend/mcp_server/README.md).
- [Upstream Apple Silicon dependency workaround](https://github.com/jamiepine/voicebox/blob/8af7efe62fab8d33e2a5dfbedabaa45f68a5184f/backend/requirements-mlx.txt).
- [MLX-Audio Qwen cloning, Base vs CustomVoice vs VoiceDesign](https://github.com/Blaizzy/mlx-audio/blob/main/docs/models/tts/qwen3-tts.md).
- [Qwen3-TTS source/model descriptions](https://github.com/QwenLM/Qwen3-TTS).
- [Pinned MLX model card, Apache-2.0](https://huggingface.co/mlx-community/Qwen3-TTS-12Hz-0.6B-Base-bf16/tree/1eccf1cb2519b5a4e8a95b5f0544f3303568164f).

## Нюанс клонирования

В upstream `MLXTTSBackend.generate` отсутствующий reference обнуляется; несовместимая сигнатура вызывает обычный `generate`; исключение клонирования перехватывается с повторной генерацией без reference. При исключении после первого chunk старые chunks также могут остаться в буфере. Поэтому HTTP 200, status completed и непустой WAV не доказывают сохранение голосовой идентичности.

Astel patch убирает эти три пути fallback, требует точный transcript и не возвращает частичный результат после исключения. Дополнительно проверены внутренности установленного `mlx-audio==0.4.1`: его общий `generate` маршрутизирует Base/CustomVoice/VoiceDesign, а Base выбирает ICL при наличии audio, text и speech-tokenizer encoder. Поэтому одного `ref_audio` в сигнатуре недостаточно: проверяем Base config, speech encoder и speaker encoder.

`instruct` в этом Voicebox MLX Base-пути игнорировался. Реестр upstream уже помечает Base как `supports_instruct=False`, хотя некоторые overview docs формулируют это шире. Реализация и model-specific API имеют приоритет: patch явно отказывает в такой инструкции. Лёгкий естественный Slavic accent — цель слухового A/B собственного английского reference, а не подтверждённая настройка движка.

Из истории upstream: `3c1e851` обходит конфликт transformers 5.x через `--no-deps`; `f750596` добавляет этот путь в Mac setup. Поэтому в пилоте сохранены `transformers==4.57.6`, `mlx-audio==0.4.1`, `mlx-lm==0.31.1`, две последние библиотеки ставятся отдельно без dependency resolution. Это известное расхождение declared dependencies; работа всего набора движков не заявляется. Октябрьские изменения `63899fd`, `fb67ad4`, `cffe24f` исправляют lifetime/освобождение MLX модели. Single-thread executor и эти исправления сохранены.

## Почему Mac сейчас

На текущей машине подтверждены arm64, 16 GiB RAM, доступный Metal. Загрузка pinned 0.6B через настоящий API прошла. Это достаточное основание для короткого локального пилота, но не benchmark скорости синтеза и не обещание достаточной памяти для одновременного тяжёлого монтажа.

Voicebox допускает отдельный удалённый backend; desktop frontend можно оставить на Mac. Перенос inference на Kevin или GPU server имеет смысл после одинакового голосового теста с замером времени и памяти. Сейчас добавлять зависимость от второго компьютера не нужно. Для удалённого доступа требуется отдельная защищённая связь: client-id MCP header не заменяет authentication.

## Контракт интеграции

`POST /profiles` → multipart `POST /profiles/{id}/samples` → `POST /generate` → JSON `GET /history/{generation_id}` → `GET /audio/{generation_id}`. `/generate/{id}/status` — SSE, а не JSON polling endpoint. Personality rewriting выключен; request text остаётся точным.

REST подходит для сохраняемых монтажных файлов. MCP полезен для управления агентом, но `voicebox_speak` запускает speaker playback. Модель/сервис не нужно встраивать в OpenReel core: передаём WAV и manifest. До приёмки голоса ни editor automation, ни публикация этим кодом не вызываются.

В первой реализации не подключаются GTA6 grammar, social accounts, чужие reference, внешний TTS provider или автоматический поиск материала. Позднее 27 октября получен собственный reference владельца и выполнен первый локальный русский TTS-пилот. Владелец подтвердил узнаваемость собственного голоса в коротком русском примере. Приёмка длинной речи, английского произношения и полного production workflow остаётся незавершённой.
