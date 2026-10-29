# OpenReel → Canvas → existing Hub

Acceptance baseline: 28 October 2026. Branch `integration/astel-media-canvas-stack`. The two explicitly approved existing Railway services were deployed; no new service or key was created. Production publishing configuration is unchanged; paid planner is OFF. **29 October recovery:** Hub is online on the same approved source; Telegram was separately stopped at the owner's request and PR #36 remains on hold. See [current recovery evidence](RECOVERY_2026-10-29.json).

## Verified path

The existing warehouse story (41.024 seconds) was uploaded once to its private delivery copy. The owner separately authorized link-reader access only to that final MP4. RAW, voice references and source folders remain private. The deployed Hub then fetched all **25,369,940 bytes**, `video/mp4`, and matched SHA-256 `bf339a949a9c56e38fd47ebbc1e062581856ac1cc290b8a48a8d51f7b5a39123` (latest proof `2026-10-29T00:54:08.014Z`). This is actual server execution, not the earlier Mac compatibility probe.

At the original acceptance, plan `b646292fa99901255470464af0ac2508ae37604a9ec100edbf70aae33abea2fa` was `simulation` / `NEEDS_APPROVAL`, approval false. `request_review` sent it for owner review. The 29 October recovery READ now finds `APPROVED` with an existing approval timestamp `2026-10-29T01:46:27.954Z`. It still has mode **simulation**, delivery **DRAFT**, attempts **0**, receipt absent. Recovery did not approve, schedule or publish it.

| Service | Delivered source | Deployment |
|---|---|---|
| Existing lazy-distribution Hub | [PR #10](https://github.com/asteloleh-gif/asteloleh-gif-astel-lazy-distribution/pull/10), `816b50d` | `030c59b8-2570-42a2-8f65-1729b7f44d90`, SUCCESS |
| Existing astel-assistant Canvas | [PR #35](https://github.com/asteloleh-gif/astel-telegram/pull/35), `4c05a67` | `40a311e7-8463-4589-836c-2a692e20c09f`, SUCCESS |

The deployed Canvas JS matches the reviewed bundle byte-for-byte. Unauthenticated POST returns 401; signed-owner authorization and stale binding checks passed unit tests. A physical signed Telegram owner/phone session has **not** been tested. Local Canvas already displays the same real plan and full server verification.

## Mac actions

1. OpenReel Astel → AI Generate → Материалы и истории → Для Canvas → **Открыть Canvas на Mac** (`http://127.0.0.1:17531/`).
2. Choose the exact story revision. **Передать тестовый черновик в Hub** reserves one durable binding and creates only `simulation`. Reuse the existing request after a recoverable error.
3. If needed, **Повторно войти в Google Drive** uses the existing local client/account and scope `drive.file`. The owner completes security warnings and Google login. **Продолжить передачу** resumes the same reserved file/job.
4. Upload lands in a separate app-owned Astel Video Delivery folder. Remote metadata/hash/size readback precedes Hub preview/submit/status. Lost replies are reconciled before retry; an unknown outcome is not cancelled or silently hidden.
5. Server fetching needs explicit owner consent for reader access to that copy. **Разрешить чтение этой копии MP4** uses reader/allowFileDiscovery=false; it never shares the whole folder. Current test copy already has the required consent/access.
6. **Проверить весь MP4 на сервере** performs the bounded server fetch and binding/hash validation. **Передать на согласование в Canvas** requests review of that exact plan/digest. Editorial acceptance on Mac does not grant publication approval.
7. Existing protected Canvas owner review uses the existing Hub. This integration does not approve, schedule or dispatch publication. A new MP4/script needs a new story revision; changed caption/account/slot gets a new delivery revision.

## Contracts and credentials

`hub_delivery.py` permits the fixed existing project/origin and simulation handoff only. `workspace_cloud.py` exposes bounded prepare/review/planning calls without owner approval credentials. Private operator and reader credentials stay in `~/.config/astel-distribution/`, never in HTML/JavaScript/Git. Google tokens, OAuth callback and auth code stay outside Canvas responses. The narrow existing Drive OAuth helper is reused; no destination switch or new grant is introduced.

The Hub stores bounded video bindings/media proofs/feedback in the existing journal and rejects stale approval digests. New planner route is guarded by `VIDEO_PLANNER_ENABLED=false`; the local owner policy is also false. No real AI request was made. The Telegram BFF authenticates the signed owner before writes, uses its existing server-held owner credential and enforces the fixed project. It does not expose credentials to the client.

Scoped checks: Hub/Radar 184 passed; Telegram 104 existing tests plus 2 new contract tests passed; Python workspace/story/voice/discovery/handoff 119 passed. Current native/UI/MCP evidence is in [STACK_VALIDATION_2026-10-28.json](STACK_VALIDATION_2026-10-28.json). [Earlier handoff evidence](HUB_HANDOFF_VALIDATION_2026-10-28.json) records the preceding DRAFT phase, before the approved cloud rollout.

## Setup and rollback

Re-run `scripts/setup_media_workspace_mac.py --node /absolute/path/to/node --cloud-planner off --start-canvas` to refresh the private Mac runtime; catalogue/media/owner HTML remain. This does not create Hub or Google credentials. Original OpenReel, accepted Amazon and `main` remain preserved.

Cloud rollback (only if needed): restore existing Hub source to `22a9ff9ce14a8f716aaf449d97fcdab8941b3191` on `review/unified-distribution-hub-20261024`, and Telegram source to `6d058c880718a5cdb0cf7e26c71ae94be36c5f14` on `review/distribution-fallback-20261024`; disable the new VIDEO_WORKSPACE_ENABLED flags. Keep `VIDEO_PLANNER_ENABLED=false`, all other variables and the existing `/data` volume. Do not replace the journal, rotate credentials or change publishing. Cloud rollback is documented, not exercised in production.
