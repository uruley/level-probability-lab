"""Download pinned public model weights only; never contacts Databento."""
import json
from pathlib import Path

from huggingface_hub import hf_hub_download

ROOT = Path(__file__).resolve().parents[1]
REVISION = "2b554741eca47781b64468546e77fef3e85130e6"

if __name__ == "__main__":
    cache = ROOT / "data" / "models" / "hub"
    for model, revision in [
        ("NeoQuasar/Kronos-base", REVISION),
        ("NeoQuasar/Kronos-Tokenizer-base", "0e0117387f39004a9016484a186a908917e22426"),
    ]:
        for filename in ("config.json", "model.safetensors"):
            path = hf_hub_download(model, filename, revision=revision, cache_dir=cache)
            print(json.dumps({"model": model, "file": filename, "path": path}), flush=True)
