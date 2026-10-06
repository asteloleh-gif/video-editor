# Astel Dialogue / Dubbing Pipeline — P0/P1

## Current production benchmark

CapCut dialogue/speech removal is the quality benchmark.
Do not remove CapCut from the workflow until Astel passes side-by-side listening tests.

## P0 — Separate Voice (CapCut benchmark)

Required editor action:

`SEPARATE VOICE`

This follows the useful CapCut interaction model shown by Oleg:

Original mixed audio
→ AI separation
→ VOICE stem
→ BACKGROUND stem

After separation the user can choose:
- Keep Voice
- Remove Voice
- Keep Both
- Solo Voice
- Solo Background
- Restore Original
- A/B Original vs Separated

Goal:
- isolate spoken/sung human voice from the mixed source;
- preserve useful ambience, impacts, room sound, game/action sound, laughter/noise where the separation model classifies it as background;
- for the current AstelFam workflow, Remove Voice is the primary action so Russian dialogue can be removed while the background bed remains;
- later the Voice stem may be replaced by an English dub while Background remains intact.

The operation must be non-destructive. Never overwrite or discard the original mixed audio.

UI should show separation progress and explicit state:
- Not separated
- Separating 0–100%
- Ready
- Error / retry
- Voice enabled/disabled
- Background enabled/disabled

The timeline should expose the stems as independently editable audio tracks when expanded.

## P1 — Dubbing

Required flow:

Original media
→ dialogue separation
→ preserved ambience/SFX bed
→ transcript
→ translation/adaptation
→ English voice track
→ timing/alignment
→ ambience + voice + music/SFX mix
→ loudness check
→ final export

Keep independent editable tracks:
- ORIGINAL
- DIALOGUE / SPEECH
- AMBIENCE / SFX
- DUB
- MUSIC
- EDIT SFX

## Channel Kits

Each channel kit can define:
- default dubbing language
- approved voices
- dialogue-removal preset
- dialogue/music/SFX target levels
- SFX asset pack
- meme/reaction asset pack
- caption preset
- motion/edit presets

Initial kits:
- ASTELFAM_V1
- ASAP_GTA6_V1

## Acceptance benchmark

Test the same 5 representative clips in CapCut and Astel:
1. clean indoor speech
2. speech + laughter
3. speech + impacts/game sounds
4. speech + background music
5. overlapping speakers/noisy room

Blind/listening review must judge:
- speech leakage
- damage to ambience/SFX
- metallic artifacts
- pumping
- intelligibility of retained non-speech audio

CapCut remains fallback until Astel is acceptable on the representative set.
