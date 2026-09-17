from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from .fcpxml import write_fcpxml
from .pipeline import analyze, process, save_plan
from .probe import executable
from .vision import DEFAULT_MODEL

VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".mkv"}


def _add_analysis_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--mode", choices=["vision", "hybrid", "motion", "audio"], default="vision")
    parser.add_argument("--motion-threshold", type=float, default=0.018)
    parser.add_argument("--sample-fps", type=float, default=4.0)
    parser.add_argument("--audio-noise-db", type=float, default=-35.0)
    parser.add_argument("--min-silence", type=float, default=0.35)
    parser.add_argument("--merge-gap", type=float, default=0.70)
    parser.add_argument("--margin-before", type=float, default=0.35)
    parser.add_argument("--margin-after", type=float, default=0.90)
    parser.add_argument("--min-segment", type=float, default=0.15)
    parser.add_argument("--vision-model", default=DEFAULT_MODEL)
    parser.add_argument("--vision-step", type=float, default=1.0, help="Seconds between sampled frames")
    parser.add_argument("--vision-batch-frames", type=int, default=20)
    parser.add_argument("--vision-overlap-frames", type=int, default=3)
    parser.add_argument("--vision-max-width", type=int, default=480)
    parser.add_argument("--vision-min-confidence", type=float, default=0.45)
    parser.add_argument("--vision-merge-gap", type=float, default=1.25)


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
        "vision_model": args.vision_model,
        "vision_step": args.vision_step,
        "vision_batch_frames": args.vision_batch_frames,
        "vision_overlap_frames": args.vision_overlap_frames,
        "vision_max_width": args.vision_max_width,
        "vision_min_confidence": args.vision_min_confidence,
        "vision_merge_gap": args.vision_merge_gap,
    }


def _open_resolve() -> None:
    if sys.platform != "darwin":
        return
    subprocess.run(["open", "-a", "DaVinci Resolve"], check=False)


def _reveal(path: Path) -> None:
    if sys.platform == "darwin":
        subprocess.run(["open", "-R", str(path.resolve())], check=False)


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

    try:
        import openai  # noqa: F401
        checks["openai_sdk"] = True
    except Exception:
        checks["openai_sdk"] = False

    key_file = Path.home() / ".config" / "video-editor" / "openai_api_key"
    checks["openai_api_key"] = bool(os.getenv("OPENAI_API_KEY", "").strip()) or (
        key_file.exists() and bool(key_file.read_text(encoding="utf-8").strip())
    )

    print(json.dumps(checks, indent=2))
    required_ok = (
        checks["ffmpeg"]
        and checks["ffprobe"]
        and checks["opencv"]
        and checks["openai_sdk"]
        and checks["openai_api_key"]
    )
    print("\nV1 vision core: " + ("OK" if required_ok else "MISSING DEPENDENCIES OR API KEY"))
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
    payload = {
        "status": "complete",
        "mode": plan.mode,
        "input": str(source.resolve()),
        "output": str(output.resolve()),
        "duration_original_sec": plan.source.duration,
        "duration_kept_sec": plan.duration_kept,
        "duration_removed_sec": plan.duration_removed,
        "percent_removed": plan.percent_removed,
        "segments_kept": len(plan.keep),
        "vision_detections": len(plan.vision_detections),
    }
    if args.resolve:
        timeline = Path(args.resolve_output).expanduser() if args.resolve_output else output.with_suffix(".fcpxml")
        write_fcpxml(plan, timeline, project_name=f"{source.stem}_rough")
        payload["resolve_timeline"] = str(timeline.resolve())
        if args.open_resolve:
            _open_resolve()
            _reveal(timeline)
    print(json.dumps(payload, indent=2))
    return 0


def cmd_resolve(args: argparse.Namespace) -> int:
    source = Path(args.video).expanduser()
    output = Path(args.output).expanduser() if args.output else Path("output") / f"{source.stem}_rough.fcpxml"
    plan = analyze(source, **_analysis_options(args))
    write_fcpxml(
        plan,
        output,
        project_name=args.project_name or f"{source.stem}_rough",
        width=args.width,
        height=args.height,
    )
    payload = {
        "status": "complete",
        "input": str(source.resolve()),
        "resolve_timeline": str(output.resolve()),
        "segments_kept": len(plan.keep),
        "duration_kept_sec": plan.duration_kept,
    }
    if args.open_resolve:
        _open_resolve()
        _reveal(output)
    print(json.dumps(payload, indent=2))
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
            output = output_dir / f"{source.stem}_rough.mp4"
            plan = process(source, output, **_analysis_options(args))
            if args.resolve:
                write_fcpxml(plan, output_dir / f"{source.stem}_rough.fcpxml")
        except Exception as exc:
            failures += 1
            print(f"ERROR: {exc}", file=sys.stderr)
    print(f"Done. Success={len(videos) - failures}, Failed={failures}")
    return 1 if failures else 0


def main() -> None:
    parser = argparse.ArgumentParser(prog="video-editor", description="AI-assisted short-form rough-cut pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    doctor = sub.add_parser("doctor", help="Check dependencies and vision configuration")
    doctor.set_defaults(func=cmd_doctor)

    analyze_parser = sub.add_parser("analyze", help="Create an edit plan without rendering")
    analyze_parser.add_argument("video")
    analyze_parser.add_argument("-o", "--output", help="Optional JSON plan output")
    _add_analysis_args(analyze_parser)
    analyze_parser.set_defaults(func=cmd_analyze)

    process_parser = sub.add_parser("process", help="Analyze and render one rough cut")
    process_parser.add_argument("video")
    process_parser.add_argument("-o", "--output")
    process_parser.add_argument("--resolve", action="store_true", help="Also write an FCPXML timeline for DaVinci Resolve Free")
    process_parser.add_argument("--resolve-output", help="Optional FCPXML output path")
    process_parser.add_argument("--open-resolve", action="store_true", help="Launch Resolve and reveal the generated FCPXML")
    _add_analysis_args(process_parser)
    process_parser.set_defaults(func=cmd_process)

    resolve_parser = sub.add_parser("resolve", help="Analyze and export an FCPXML timeline for DaVinci Resolve Free")
    resolve_parser.add_argument("video")
    resolve_parser.add_argument("-o", "--output")
    resolve_parser.add_argument("--project-name")
    resolve_parser.add_argument("--width", type=int, default=1080)
    resolve_parser.add_argument("--height", type=int, default=1920)
    resolve_parser.add_argument("--open-resolve", action="store_true")
    _add_analysis_args(resolve_parser)
    resolve_parser.set_defaults(func=cmd_resolve)

    batch_parser = sub.add_parser("batch", help="Process a folder")
    batch_parser.add_argument("folder", nargs="?", default="input")
    batch_parser.add_argument("--output-dir", default="output")
    batch_parser.add_argument("--resolve", action="store_true", help="Also write FCPXML timelines")
    _add_analysis_args(batch_parser)
    batch_parser.set_defaults(func=cmd_batch)

    args = parser.parse_args()
    raise SystemExit(args.func(args))


if __name__ == "__main__":
    main()
