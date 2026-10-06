# OpenReel iOS — parked candidate

Status: PARKED / SOURCE NOT PUBLIC

OpenReel has an iOS implementation described extensively in the public repository,
but the actual iOS and Android source trees are intentionally excluded from the
public repository.

Evidence:
- upstream commit 3efdb84dc9655ac82778600212c4d0b008a69f82
- commit message: "Merge private main updates excluding Android and iOS apps"
- upstream .gitignore explicitly excludes:
  - /Openreel Video/
  - /Openreel Video Android/
  - /apps/ios/
  - /apps/android/

Therefore do NOT reconstruct or claim to vendor the private mobile source.

## Public material retained as reference

Public OpenReel docs describe:
- SwiftUI iOS editor architecture
- shared OpenReel project model
- timeline behavior
- crop/trim UX
- filters
- audio and mobile parity
- on-device smart-tool plans
- App Store release metadata

Useful upstream paths:
- docs/MOBILE-PARITY.md
- docs/MOBILE-PARITY-AUDIT.md
- docs/android-port/
- docs/superpowers/plans/2026-05-28-ios-trim-and-crop.md
- docs/superpowers/specs/2026-05-28-ios-trim-and-crop-design.md
- docs/superpowers/plans/2026-05-22-ios-timeline-fixes.md
- APP_STORE_SUBMISSION.txt
- STORE_RELEASE_NOTES.md

Pinned public upstream reference:
c9340465e5d37e684cc25bdbe746c4ccd45e165c

## Future options

1. If upstream republishes the mobile source, vendor/fork it here while preserving
   its license and notices.
2. If legitimate repository access is granted, import it through the normal
   authorized Git workflow.
3. Otherwise, build an Astel mobile companion using the public project schema and
   documented UX only, without copying unavailable private implementation.

This mobile candidate is intentionally not on the critical path. Mac Desktop +
MCP remains Stage 1.
