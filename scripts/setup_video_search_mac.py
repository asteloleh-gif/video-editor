#!/usr/bin/env python3
"""Install isolated, pinned metadata search; never changes Voicebox dependencies."""
from pathlib import Path
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile

REPO = Path(__file__).resolve().parent.parent
HOME = Path.home() / ".local/share/astel-video-search"


def main():
    if platform.system() != "Darwin" or sys.version_info < (3, 11):
        raise SystemExit("Use Python 3.11+ on macOS")
    HOME.mkdir(parents=True, exist_ok=True, mode=0o700)
    python = HOME / "venv/bin/python"
    if not python.exists():
        subprocess.run([sys.executable, "-m", "venv", str(HOME / "venv")], check=True)
    subprocess.run([str(python), "-m", "pip", "install", "--require-hashes", "--no-deps", "-r", str(REPO / "integration/video-search/requirements-mac.txt")], check=True)
    target = HOME / "src/video_editor"
    target.mkdir(parents=True, exist_ok=True, mode=0o700)
    for name in ("__init__.py", "video_search.py"):
        with tempfile.NamedTemporaryFile(dir=target, delete=False) as stream:
            tmp = Path(stream.name)
            stream.write((REPO / "src/video_editor" / name).read_bytes())
        tmp.chmod(0o600)
        os.replace(tmp, target / name)
    # Preserve upstream license text in the installed runtime.
    site = Path(subprocess.check_output([str(python), "-c", "import sysconfig; print(sysconfig.get_path('purelib'))"], text=True).strip())
    notice = next(site.glob("yt_dlp-*.dist-info/licenses/LICENSE"), None)
    if notice:
        shutil.copyfile(notice, HOME / "LICENSE.yt-dlp")
    (HOME / "runtime.json").write_text(json.dumps({"package": "yt-dlp", "version": "2026.10.26", "mode": "metadata_only", "paid_api": False, "media_downloads": False}, indent=2) + "\n")
    print("Astel Video Search installed locally. No API key or paid service required.")


if __name__ == "__main__":
    main()
