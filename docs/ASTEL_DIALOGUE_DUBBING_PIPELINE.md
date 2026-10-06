# Astel Dialogue / Dubbing Pipeline — P0/P1

## Current production benchmark

CapCut dialogue/speech removal is the quality benchmark.
Do not remove CapCut from the workflow until Astel passes side-by-side listening tests.

## P0 — Remove Dialogue

Required editor action:

`REMOVE DIALOGUE`

Goal:
- remove spoken Russian/Ukrainian dialogue;
- preserve useful ambience, impacts, room sound, game/action sound and other non-dialogue audio as well as practical;
- never silently mute the whole clip unless the user explicitly chooses Mute.

UI states:
- Original
- Dialogue Removed
- Compare A/B
- Restore Original

The operation must be non-destructive.

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
