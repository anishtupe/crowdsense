"""Download the CLIP ViT-B/32 ONNX vision model used by vision_service.

Source: Hugging Face repo Xenova/clip-vit-base-patch32 (an ONNX export of
openai/clip-vit-base-patch32), pinned to one revision and checked by sha256.

    python scripts/fetch_vision_model.py              # runtime file only (~89 MB)
    python scripts/fetch_vision_model.py --with-text  # + text model and tokenizer
                                                      #   (~254 MB, only needed to run
                                                      #   scripts/build_vision_prompts.py)

Files go to VISION_MODEL_DIR (default backend/models/clip-vit-b32/, git-ignored).
The repo lives in OneDrive, which will sync these files; point
VISION_MODEL_DIR in .env at a folder outside OneDrive to avoid that.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.vision_service import _model_dir  # noqa: E402

REPO = "Xenova/clip-vit-base-patch32"
REVISION = "d15189d7028b43f1d3e65039190477f6af591c2a"
MODEL_DIR = _model_dir()
USER_AGENT = "CrowdSense-academic-project/0.1 (model download script)"

# (path in repo, sha256 or None for small non-LFS files)
VISION_FILES = [
    ("onnx/vision_model_quantized.onnx",
     "583fd1110a514667812fee7d684952aaf82a99b959760c8d7dca7e0ab9839299"),
]
TEXT_FILES = [
    ("onnx/text_model.onnx",
     "3f6571f5bad13a97c469c1622e1cfc4d9aef78b79fdbfcff804ca357bfada8cc"),
    ("tokenizer.json", None),
]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _fetch(repo_path: str, expected_sha: str | None) -> None:
    dest = MODEL_DIR / Path(repo_path).name
    if dest.exists() and (expected_sha is None or _sha256(dest) == expected_sha):
        print(f"ok (cached)  {dest.name}")
        return
    url = f"https://huggingface.co/{REPO}/resolve/{REVISION}/{repo_path}"
    print(f"downloading {url}")
    tmp = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as resp, tmp.open("wb") as out:
        for chunk in iter(lambda: resp.read(1 << 20), b""):
            out.write(chunk)
    if expected_sha is not None:
        actual = _sha256(tmp)
        if actual != expected_sha:
            tmp.unlink()
            sys.exit(f"sha256 mismatch for {repo_path}: got {actual}")
    tmp.replace(dest)
    print(f"ok           {dest.name}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--with-text", action="store_true",
                        help="also fetch the text model + tokenizer (prompt building only)")
    args = parser.parse_args()

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    for repo_path, sha in VISION_FILES + (TEXT_FILES if args.with_text else []):
        _fetch(repo_path, sha)


if __name__ == "__main__":
    main()
