"""Download the reviewed 0.6B checkpoint to the isolated local runtime."""

import json
import hashlib
from pathlib import Path
import shutil

from runtime import HERE, HOME


def main():
    from huggingface_hub import snapshot_download

    spec = json.loads((HERE / "models.json").read_text())["0.6B"]
    target = HOME / "models/0.6B"
    if target.exists():
        raise FileExistsError("Model directory already exists; inspect it instead of overwriting")
    if shutil.disk_usage(HOME).free < spec["bytes"] * 2 + 2_000_000_000:
        raise RuntimeError("Need at least 7.1 GB free for model download and validation")
    cached = Path(snapshot_download(spec["repository"], revision=spec["revision"], cache_dir=HOME / "hub"))
    for expected in spec["files"]:
        path = cached / expected["file"]
        digest = hashlib.sha256()
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(8 * 1024 * 1024), b""):
                digest.update(chunk)
        if path.stat().st_size != expected["bytes"] or digest.hexdigest() != expected["sha256"]:
            raise RuntimeError(f"Model checksum mismatch: {expected['file']}")
    # A symlink uses the exact cached snapshot without a second copy of the weights.
    target.parent.mkdir(parents=True, exist_ok=True)
    target.symlink_to(cached, target_is_directory=True)
    (HOME / "model-receipt.json").write_text(json.dumps({"size": "0.6B", **spec, "snapshot": str(cached)}, indent=2) + "\n")
    print(json.dumps({"model": str(target), "revision": spec["revision"]}, indent=2))


if __name__ == "__main__":
    main()
