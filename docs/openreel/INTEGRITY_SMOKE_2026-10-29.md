# Short pipeline integrity check — 29 October 2026

Owner requested one short example using existing material, with emphasis on system integrity rather than editing polish. No new stack or renderer code was needed.

## Actual run

In installed OpenReel Astel, created a separate 1080×1920 / 30 fps project, selected the two existing Commons warehouse video assets, entered two short Russian paragraphs and clicked **Собрать новый черновик**. The existing local Oleg RU/B voice generated both scenes; local Whisper produced timestamps; the installed renderer produced a new MP4. No per-story terminal render command was used. Shell checks below inspected the resulting files only.

- Project: `b2d6e5cb-2fbb-4491-ad7b-b37560c6b9bc`; saved-project key from `list_projects`: `b2d6e5cb-2fbb-4491-ad7b-b37560c6b9bc-slot-2`.
- Story/job: `942825ca-7a5d-4299-a8bf-d45c5f76bb99`, title **Один клик — целый склад · тест цепочки**.
- MP4: 10.048 seconds including AAC padding; video 10.000 seconds, H.264 1080×1920, AAC stereo 48 kHz, 4,840,107 bytes.
- SHA-256: `4ffe3b9e82528cd0e40c9ea57660f2222652c8315b665f5f082663a89a4d964b`.
- Story digest: `9f8ea3abe67fc9c6b771d0a3a700d6b24f5236264037bdff0e66fb5c79c438d0`.

The UI's **Добавить отдельные дорожки** created four tracks, three clips/media items and six overlays. Explicit save, switching to the original saved project, reopening the test saved-project key and external MCP READ preserved these counts. Clicking the same import button again after reopening left the same counts, with no duplicates. The original warehouse project remains separate. Saved-project keys include a slot suffix; `open_project` requires the exact key returned by `list_projects`, not the internal project UUID.

The local Canvas displayed the exact new story/hash. Its **Передать тестовый черновик в Hub** action uploaded a private delivery copy and received one real server `simulation` / `DRAFT` plan. After the owner explicitly authorized link-reader access to this exact new final copy, **Проверить весь MP4 на сервере** verified the full file and **Передать на согласование в Canvas** moved the same plan to `NEEDS_APPROVAL`:

- Handoff job: `b0e007c7-f2fc-4e7a-91a8-255641c9da51`.
- Hub plan: `c1703b17e455e8653e9b465e6abbab91f79934c0f6e4e55e9ae1a2c3eb1cecc0`.
- Input digest: `09522280bbd536bacd81eb1b070f23dde6744d8604be313e4307da284dfbac71`.
- Final independent Hub connector READ: `NEEDS_APPROVAL`, mode `simulation`, approval absent, delivery `DRAFT`, attempts `0`, receipt absent.

## Verification and result

Full MP4 video/audio decode exited 0 without decoder errors. Frame samples at 1.0, 4.5 and 8.5 seconds show both warehouse shots and the credit card. Audio is present: mean −23.3 dB, peak −6.3 dB; this is a signal check, not a subjective voice-quality approval. Local MCP discovery found 322 tools and the new job's READ passed. Automatic captions contain two transcription inaccuracies (for example, “простотой” became “простой”); caption polishing was deliberately excluded from this integrity run.

**PASS: existing materials → local narration/captions → MP4 → editable OpenReel → Canvas → server-verified Hub review.** The owner authorized link-reader access only to this exact new final MP4 with synthesized voice. The folder and originals were not shared. At `2026-10-29T18:05:30.049Z`, the actual deployed Hub fetched all **4,840,107 bytes**, `video/mp4`, and verified SHA-256 `4ffe3b9e82528cd0e40c9ea57660f2222652c8315b665f5f082663a89a4d964b`. Both local Canvas and independent cloud READ confirm the same plan/digest and review state. No publication approval was granted.

Separately, after cloud recovery, the Canvas's server-preflight button fetched the already-authorized **previous 41-second MP4** at `2026-10-29T17:54:16.957Z`: all 25,369,940 bytes and its existing `bf339a94…a39123` hash matched. This proves the restored server fetch path for the previous artifact; it is not a substituted proof for the new MP4.

One initial UI submission retained stale draft text and was cancelled at 5%; job `33a013a0-f525-473d-98ec-9fb781ee0719` is excluded from the successful run. The corrected request completed. No source media, voice profile, active style, publishing configuration or Telegram deployment was changed. No paid model request, approval, schedule or publish action was issued.

## Scope of completion

The requested short integrity test is complete through server verification and the review queue. It used already-acquired materials and a supplied short script; it does not certify autonomous fact/footage discovery, physical Mac reboot, Telegram phone UI, Kevin/Windows, subjective voice polish or social publication. Telegram remains offline on owner hold. Paid AI and production publishing configuration remain unchanged. One coordinate-index review-button click was prevented by automatic review; a fresh full accessibility snapshot and the exact semantic button name resolved the ambiguity before any review mutation.

Private output/evidence remain outside Git. Machine-readable checkpoint: [INTEGRITY_SMOKE_2026-10-29.json](INTEGRITY_SMOKE_2026-10-29.json).
