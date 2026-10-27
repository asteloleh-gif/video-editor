"""Run the patched upstream API on loopback, without automatic model downloads."""

import json
import os
import sys

from runtime import HOME, SOURCE, verify_source


def main():
    receipt = verify_source()
    # Dedicated caches and database; never reuse ASAP's environments or voices.
    os.environ["VOICEBOX_MODELS_DIR"] = str(HOME / "hub")
    os.environ["ASTEL_VOICEBOX_MODEL_ROOT"] = str(HOME / "models")
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    os.environ["VOICEBOX_CLOUD_ENABLED"] = "false"
    sys.path.insert(0, str(SOURCE))
    from backend import config
    config.set_data_dir(HOME / "data")
    from backend.main import app
    import uvicorn

    @app.get("/astel/health")
    async def astel_health():
        verify_source()
        model_receipt = HOME / "model-receipt.json"
        return {
            "service": "astel-voicebox", "required_clone": True,
            "supported_engine": "qwen", "instruct_supported": False,
            "upstream_commit": receipt["upstream"]["commit"],
            "patched_backend_sha256": receipt["patched_backend_sha256"],
            "model_06b_present": (HOME / "models/0.6B/config.json").is_file(),
            "model_06b_revision": json.loads(model_receipt.read_text())["revision"] if model_receipt.is_file() else None,
        }

    print(json.dumps({"api": "http://127.0.0.1:17493", "mcp": "http://127.0.0.1:17493/mcp", "data": str(HOME / "data")}))
    uvicorn.run(app, host="127.0.0.1", port=17493)


if __name__ == "__main__":
    main()
