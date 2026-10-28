# Astel: implementation checkpoints 1–8

Owner request: complete items 1–8 in one sustained pass, with the required access authorized. Initial estimate: 8–16 hours, subject to code and acceptance results. Voice-quality work (item 9), Kevin certification and real social publication are outside this pass.

Working branch: `integration/astel-media-canvas-stack`. Baseline: `23020e3`. Preserve the accepted Amazon artifact, voice references, original OpenReel/OpenCut, synced `sources/`, production publishing configuration and unrelated local work. No implementation agents or parallel rewrite are being created.

| Item | Implementation and acceptance | Checkpoint |
|---|---|---|
| 1. Canvas approval | Exact story/plan digest; request changes and owner approval; stale or unauthenticated actions rejected; same existing Hub | Auditing existing Telegram owner guard and Canvas package |
| 2. Server media readiness | Existing server fetches the exact MP4 and reports actual type/size/hash; no publication or provider dispatch | Baseline is real DRAFT plus anonymous full download from Mac; deployed fetch remains unverified |
| 3. Durable operation | User LaunchAgent supervisor; restart recovery without duplicate workers; bounded backlog; disk checks; recoverable cache retention; health in Canvas | Implemented and installed; 30 scoped tests; real queued Commons search recovered by a separate supervisor, then preserved across its process restart. Physical Mac reboot not tested. |
| 4. Own discovery | Persistent topic watches, timed observations and measured growth; bounded acquisition; source provenance and deduplication; provider failures remain visible | Existing search/catalogue is the baseline |
| 5. Story planning | Grounded script and explicit per-scene source choices, time ranges and evidence; editable proposal before rendering | Existing manual script form is the baseline |
| 6. Editable OpenReel | Separate media scenes, narration, text/captions and supported motion; actual project binding and grouped Undo/Redo | Existing flattened MP4 import stays available |
| 7. MCP | Typed, bounded workspace tools on existing Desktop MCP; tool discovery and real READ/job smoke; no arbitrary shell or publishing tools | Existing core MCP stays intact |
| 8. Corrections/style | Structured version-bound feedback; auditable style candidates; explicit owner activation; next story records exact applied style | Existing editorial remarks and old RAW OLEH_STYLE stay intact |

Each completion entry must identify a commit/change, checks actually run, and a remaining limitation. A local unit test, uploaded file, installed app, connected tool and deployed worker acceptance are distinct states. Do not declare all eight done from one smoke test.

Cloud source baseline verified read-only: existing Hub service is on `review/unified-distribution-hub-20261024`, deployed commit `22a9ff9ce14a8f716aaf449d97fcdab8941b3191`. Other checkouts/tasks are reference-only; any necessary cloud edits use isolated checkouts. No credentials, source media, unlisted delivery links or private historical Canvas HTML enter Git.

## Durable runtime evidence

The user LaunchAgent `us.astel.media-workspace.worker` scans the existing SQLite queue every 20 seconds, limits child workers to four and pending intents to 100, and pauses media acquisition/rendering below 8 GiB free. Failed jobs require an explicit retry. Its heartbeat is shown in Canvas. A login restarts the user service; this is not a system daemon while logged out.

Verified old per-job asset duplicates may be pruned after seven days, only when their intact library source and hashes match. A durable restore map precedes deletion. RAW, library originals, narration, final MP4, voice references and unknown files are preserved. Restore uses `python -m video_editor.workspace_runtime cache-restore --id <job UUID>`.

Checks: `tests/test_workspace_runtime.py`, `tests/test_media_workspace.py`, `tests/test_workspace_canvas.py`: 30 passed. Private process recovery evidence is in the workspace runtime's `validation/recovery-20261028/result.json`. The real test used an isolated catalogue, completed one Commons search, restarted its supervisor, and retained exactly one job. The main catalogue was not used as a destructive restart fixture. Installer handles the observed asynchronous launchd bootout/bootstrap race with bounded retries of the same user plist.
