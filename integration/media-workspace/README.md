# OpenReel Astel media workspace patch

`0001-openreel-astel-workspace.patch` is cumulative over OpenReel `c9340465e5d37e684cc25bdbe746c4ccd45e165c`. It includes the earlier local Voicebox, metadata search and prepared-story assembly patches. Apply only this cumulative patch to that clean pin; do not stack it on the earlier cumulative patches.

The `vendor/openreel` checkout stays unchanged. `render.cjs` is the fixed private generic-story renderer installed by `scripts/setup_media_workspace_mac.py`. Full workflow, limits, setup, migration map and remaining Canvas/Hub connection steps: [MEDIA_WORKSPACE.md](../../docs/openreel/MEDIA_WORKSPACE.md).

OpenReel upstream MIT notices remain in the candidate app. No source media, personal voice reference, endpoint descriptor or credentials belong in this folder.
