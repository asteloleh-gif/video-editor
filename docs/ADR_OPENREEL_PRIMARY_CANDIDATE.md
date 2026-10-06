# ADR — OpenReel as Primary Astel Editor Candidate

Date: 2026-10-06
Status: ACTIVE CANDIDATE / DO NOT DELETE FALLBACKS YET

## Decision

OpenReel is the primary candidate for the Astel Video Editor core.

Why:
- existing desktop MCP;
- headless agent runner;
- large editing tool registry;
- project/timeline core separated from agent layer;
- transactional AI edits with undo/dry-run;
- Motion Creator;
- proxy infrastructure;
- learned spectral noise profiles;
- browser + desktop surfaces.

## Astel layers to preserve/build

- Channel Kits: ASTELFAM_V1, ASAP_GTA6_V1
- Asset Packs: approved SFX, memes, PNGs, motion assets
- Edit Presets: Reaction, Fail, Win, Replay, Score, GTA callouts
- OLEH_STYLE correction learning
- performance/proxy status UX
- Separate Voice / dialogue-removal workflow
- saved noise profiles (hair dryer, AC, room tone, etc.)
- English dubbing workflow
- Remotion/Emil layer where it adds value beyond OpenReel Motion Creator

## Deployment

Web candidate:
https://openreel-web-production.up.railway.app

Pinned upstream commit for initial web deployment:
c9340465e5d37e684cc25bdbe746c4ccd45e165c

Desktop/MCP:
Use official OpenReel Desktop on Mac for the first live MCP test.

## Migration rule

Do not delete OpenCut, AstelFam Editor, or the legacy video-editor pipeline until OpenReel passes:
1. Mac desktop MCP round-trip;
2. proxy/performance usability test;
3. editable AI changes + human correction readback;
4. export validation;
5. dialogue/noise workflow comparison.

After pass, deprecate losing editor paths deliberately.
