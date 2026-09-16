from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from .pipeline import analyze, process, save_plan
from .probe import executable

VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".mkv"}


def _add_analysis_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--mode", choices=["hybrid", "motion", "audio"], default="hybrid")
    parser.add_argument("--motion-threshold", type=float, default=0.018)
    parser.add_argument("--sample-fps", type=float, default=4.0)
    parser.add_argument("--audio-noise-db", type=float, default=-35.0)
    parser.add_argument("--min-silence", type=float, default=0.35)
    parser.add_argument("--merge-gap", type=float, default=0.70)
    parser.add_argument("--margin-before", type=float, default=0.25)
    parser.add_argument("--margin-after", type=float, default=0.90)
    parser.add_argument("--min-segment", type=float, default=0.15)


def _analysis_options(args: argparse.Namespace) -> dict:
    return {
        "mode": args.mode,
        "motion_threshold": args.motion_threshold,
        "sample_fps": args.sample_fps,
        "audio_noise_db": args.audio_noise_db,
        "min_silence": args.min_silence,
        "merge_gap": args.merge_gap,
        "margin_before": args.margin_before,
        "margin_after": args.margin_after,
        "min_segment": args.min_segment,
    }


def cmd_doctor(_: argparse.Namespace) -> int:
    checks = {
        "ffmpeg": executable("ffmpeg"),
        "ffprobe": executable("ffprobe"),
        "auto-editor_optional": executable("auto-editor"),
        "node_optional": executable("node"),
    }
    try:
        import cv2  # noqa: F401
        checks["opencv"] = True
    except Exception:
        checks["opencv"] = False

    print(json.dumps(checks, indent=2))
    required_ok = checks["ffmpeg"] and checks["ffprobe"] and checks["opencv"]
    print("\nV0 core: " + ("OK" if required_ok else "MISSING DEPENDENCIES"))
    return 0 if required_ok else 1


def cmd_analyze(args: argparse.Namespace) -> int:
    plan = analyze(args.video, **_analysis_options(args))
    payload = plan.to_dict()
    if args.output:
        save_plan(plan, args.output)
        payload["plan_file"] = str(Path(args.output).expanduser().resolve())
    print(json.dumps(payload, indent=2))
    return 0


def cmd_process(args: argparse.Namespace) -> int:
    source = Path(args.video).expanduser()
    output = Path(args.output).expanduser() if args.output else Path("output") / f"{source.stem}_rough.mp4"
    plan = process(source, output, **_analysis_options(args))
    print(json.dumps({
        "status": "complete",
        "input": str(source.resolve()),
        "output": str(output.resolve()),
        "duration_original_sec": plan.source.duration,
        "duration_kept_sec": plan.duration_kept,
        "duration_removed_sec": plan.duration_removed,
        "percent_removed": plan.percent_removed,
        "segments_kept": len(plan.keep),
    }, indent=2))
    return 0


def cmd_batch(args: argparse.Namespace) -> int:
    folder = Path(args.folder).expanduser()
    output_dir = Path(args.output_dir).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)
    videos = sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS)
    if not videos:
        print("No supported videos found.")
        return 0

    failures = 0
    for index, source in enumerate(videos, start=1):
        print(f"[{index}/{len(videos)}] {source.name}")
        try:
            process(source, output_dir / f"{source.stem}_rough.mp4", **_analysis_options(args))
        except Exception as exc:
            failures += 1
            print(f"ERROR: {exc}", file=sys.stderr)
    print(f"Done. Success={len(videos) - failures}, Failed={failures}")
    return 1 if failures else 0


def main() -> None:
    parser = argparse.ArgumentParser(prog="video-editor", description="Local-first short-form rough-cut pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    doctor = sub.add_parser("doctor", help="Check dependencies")
    doctor.set_defaults(func=cmd_doctor)

    analyze_parser = sub.add_parser("analyze", help="Create an edit plan without rendering")
    analyze_parser.add_argument("video")
    analyze_parser.add_argument("-o", "--output", help="Optional JSON plan output")
    _add_analysis_args(analyze_parser)
    analyze_parser.set_defaults(func=cmd_analyze)

    process_parser = sub.add_parser("process", help="Analyze and render one rough cut")
    process_parser.add_argument("video")
    process_parser.add_argument("-o", "--output")
    _add_analysis_args(process_parser)
    process_parser.set_defaults(func=cmd_process)

    batch_parser = sub.add_parser("batch", help="Process a folder")
    batch_parser.add_argument("folder", nargs="?", default="input")
    batch_parser.add_argument("--output-dir", default="output")
    _add_analysis_args(batch_parser)
    batch_parser.set_defaults(func=cmd_batch)

    args = parser.parse_args()
    raise SystemExit(args.func(args))


if __name__ == "__main__":
    main()
