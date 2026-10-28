# Topic-to-video pilot: Amazon

28 October 2026. Local review only; no Hub submission or publishing configuration changes.

## Delivered

A Russian vertical story, 1080×1920 / 30 fps / H.264 + AAC, approximately 62 seconds. The owner's approved Russian Voicebox profile uses its existing 100% tempo and warm preset B. Narration is 59.243 seconds, followed by source credits.

The agent gathered 20 YouTube metadata candidates using the existing free search, reviewed alternative sources, and selected two real Amazon BHX4 warehouse videos and two photographs from Wikimedia Commons. Their CC BY 2.0/4.0 declarations, authors, dates, exact source URLs and SHA-256 hashes are recorded in `examples/story-pilot/amazon-ru.json`. Images are labelled with their actual years. The historical dates and the books/cloud scenes use original typography and illustrations rather than reconstructed archival footage.

Full source links, licenses and change notices accompany the MP4 in `SOURCES.md`; compact credits are also embedded. Company dates come from Amazon Investor Relations, the original Amazon press archive and AWS. The editorial conclusion is analysis, not a quotation from those sources.

## What this validates

```text
Topic + factual sources
  → scene plan + search queries
  → agent selection and source/license review
  → pinned local media (RAW preserved)
  → existing persistent Voicebox coordinator
  → local whisper.cpp transcript and scene anchors
  → caption text corrected against the approved script
  → repeatable Remotion render
  → MP4 imported to a separate OpenReel project for review
```

The OpenReel project contains the finished MP4 on one video track. It is a playback/review handoff, not a reconstruction of every original layer in native OpenReel. Source scenes and graphics remain editable in the `AstelStoryPilot` Remotion composition and its input JSON. Existing projects and the current Voicebox text draft were retained.

This is an agent-assisted pilot. Autonomous factual research, semantic video ranking, arbitrary topic segmentation, word-perfect forced alignment, a batch of 100 topics, production scheduling and Hub round trips are not implemented by this module. Scene anchors must be found in real ASR; a missing anchor stops the build instead of inventing timestamps. Caption corrections bind to the exact narration hash.

## Project pieces

- `src/video_editor/story_pilot.py`: reviewed acquisition, RAW hash/path checks, scene alignment, caption validation, render props, SRT and attribution sidecar.
- `examples/story-pilot/amazon-ru.json`: seven-scene brief, reviewed assets and factual sources.
- `examples/story-pilot/amazon-ru.txt`: narration text; voice references and private bindings remain outside Git.
- `remotion/src/StoryPilot.tsx`: reusable editorial layout with seven authored timeline sequences, narration, images/video, captions and original book/cloud graphics.
- Existing `src/video_editor/voicebox_jobs.py` and `transcript.py`: personal-voice generation and local transcription; no new voice service or paid AI API.

Remotion skill was already installed. This pilot adds `@remotion/media` pinned to the existing Remotion 4.0.529 version, plus local Homebrew whisper.cpp 1.9.4 and the multilingual GGML base model. It does not install a new skill or upgrade the editor. Original dependency notices remain intact; media attribution is separate.

## Repeat on the configured Mac

Use the existing Voicebox Python environment and a Node 22+ installation. FFmpeg, ffprobe, whisper-cli and `~/.cache/video-editor/whisper/ggml-base.bin` are required. Voicebox's approved `oleh-ru` binding must already be present; do not copy a personal reference into the repository.

1. Choose a new output ID/folder; keep source media under its `raw/` directory. Acquire only the pinned, reviewed files:

```bash
PYTHONPATH=src ~/.local/share/astel-voicebox/venv/bin/python -m video_editor.story_pilot \
  --brief examples/story-pilot/amazon-ru.json \
  --output output/amazon-pilot-20261028 \
  --public remotion/public/jobs/amazon-pilot-20261028 --acquire-only
```

Acquisition uses the fixed Wikimedia upload host, no credentials or cookies, a 40 MiB per-file bound and expected SHA-256. Existing RAW with different bytes is preserved and rejected. Redirects and HTTP 429 stop acquisition; there is no provider switch or automatic retry. The initial pilot encountered a rate limit, waited, and then downloaded successfully with an identified project user agent.

2. Generate narration using the existing `SpeechJobs.submit()` coordinator and a fresh UUID. The executed request is retained locally in the output folder. After status is `ready`, use `SpeechJobs.audio()` to obtain its verified path/hash, then copy it as `narration.wav`.
3. Run `transcribe_video(narration, language='ru', max_len=38)` from the existing transcript module; save its result as `transcript.json`. Review names and dates. An optional `captions-reviewed.json` contains `audio_sha256` and corrected `segments` with the real ASR timing. Automatic ASR spelling is not treated as editorially accepted text.
4. Build the timeline and credits by running the acquisition command above without `--acquire-only`.
5. From `remotion/`, open Studio for editing and render the accepted props:

```bash
./node_modules/.bin/remotion studio --no-open
./node_modules/.bin/remotion render src/index.ts AstelStoryPilot \
  ../output/amazon-pilot-20261028/amazon-pilot-ru.mp4 \
  --props ../output/amazon-pilot-20261028/props.json \
  --codec h264 --crf 19 --x264-preset fast --concurrency 2
```

Keep personal narration on the local computer. Shut down the temporary Studio server after review; it is not a hosted production service. View the exported MP4 directly or import it to a new OpenReel project. Existing read-only MCP probe restrictions remain unchanged.

## Decision after viewing

Evaluate footage relevance, text readability, voice/pace and the balance between real footage, photos and original graphics. If the format works, the next implementation is a source library and review queue around this manifest, followed by a Hub handoff for an exact approved final asset. The existing publisher remains the execution owner.

## Owner review and quality follow-up

The owner accepted v1 as a useful test pilot and requested a voice/editing quality audit. Preserve the accepted MP4 with SHA-256 `85d872aee8e3b28fdd8303be87b384c46ed53b178910125f427fdbfbe1e68480`; experiments must use separate outputs. `QUALITY_REVIEW_2026-10-28.json` records measurements, editorial hypotheses, current integration limits and a staged experiment plan.

The main visual limitation is coverage: only 16 of 59.24 narration seconds use source video, from two views of the same warehouse. Seven scenes last 6–13 seconds and repeat one card layout. First test a stronger books-to-cloud hook, more relevant shot coverage, varied full-frame footage and selective graphics in a 20-second edit. Cuts should follow the meaning of a phrase; 2–4 seconds is an experimental shot target, not a universal rule.

Voice measures 132.7 words/minute, with no detected silence longer than 0.47 seconds at the stated threshold. That does not measure expressiveness or speaker similarity. First compare phrasing, entity pronunciation and the existing warm EQ using controlled short samples; do not accelerate the whole voice by default. The current MLX Base clone rejects delivery instructions. Qwen's 1.7B Base is a candidate for an isolated comparison, not an installed or proven improvement on this M1/16 GiB Mac. The final MP4 measures -19.1 LUFS integrated and -4.5 dBTP, with no clipping detected; final mix loudness is a separate comparison from changing the global Voicebox profile.

Keep Voicebox, OpenReel, FFmpeg and Remotion. Evaluate the existing whisper.cpp token timings before adding another alignment engine; WhisperX is conditional on measured caption drift. PySceneDetect can split source shots, and a later SigLIP 2 frame/text index can rank candidate imagery, but neither is integrated or validated by this pilot. These source-processing additions cannot supply missing historical footage. Native OpenReel scene/track handoff is still needed for a practical manual correction loop: the current OpenReel project contains one flattened MP4.
