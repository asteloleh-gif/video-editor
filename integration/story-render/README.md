# OpenReel Astel assembly integration

`0001-openreel-astel-assembly.patch` is cumulative: Voicebox + video search + prepared-story assembly. Apply it **alone** to OpenReel `c9340465e5d37e684cc25bdbe746c4ccd45e165c`; do not stack it on the earlier speech/search patches. No unrelated-history merge or vendor mutation is needed.

`render.cjs` is the fixed private Remotion entry point installed outside the repository. Electron receives only package aliases/job UUIDs; the Python coordinator resolves and checks paths. Native IPC is local-only and adds no public MCP tools or publishing actions.

See [workflow, setup and migration](../../docs/openreel/STORY_ASSEMBLY.md) and [verification](../../docs/openreel/STORY_ASSEMBLY_VALIDATION_2026-10-28.json). The installer preserves original OpenReel resources/notices and includes the upstream MIT license. Copied Remotion dependencies retain their own licenses; local FFprobe notices are copied from the installed Homebrew distribution.
