"""Run photos through the vision model exactly as the server would.

    python scripts/try_vision.py photo1.jpg photo2.png
    python scripts/try_vision.py flood.jpg --text "Water entering homes near the river"

Each image is sanitised like an upload (app/media.py), then analysed
(app/services/vision_service.py). With --text, the text is classified by
nlp_service and compared with the photo (consistency / conflict).
This is a manual check, not an evaluation: it says nothing about accuracy.
"""
from __future__ import annotations

import argparse
import base64
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings  # noqa: E402
from app.media import MediaError, process_report_media, stored_image_bytes  # noqa: E402
from app.services import nlp_service, vision_service  # noqa: E402
from app.services.duplicate_detection import phash_distance  # noqa: E402

MIME = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Try the vision model on local photos.")
    parser.add_argument("images", nargs="+", type=Path)
    parser.add_argument("--text", help="report text to compare each photo with")
    args = parser.parse_args()

    settings.VISION_ENABLED = True  # this script is for trying the model
    text_label = nlp_service.classify_disaster_type(args.text) if args.text else None
    if args.text:
        print(f'text: "{args.text}" -> classified as: {text_label}\n')

    hashes = []
    for path in args.images:
        print(f"== {path.name}")
        mime = MIME.get(path.suffix.lower(), "application/octet-stream")
        uri = f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()
        try:
            image = stored_image_bytes(process_report_media(uri))
        except MediaError as exc:
            print(f"   rejected by upload checks: HTTP {exc.status_code} {exc}\n")
            continue

        start = time.perf_counter()
        result = vision_service.analyze_image(image, text_label=text_label)
        ms = (time.perf_counter() - start) * 1000
        if not result.has_evidence:
            print(f"   fallback (no vision evidence): {result.note}\n")
            continue

        print(f"   model: {result.model}   ({ms:.0f} ms)")
        for label, p in sorted(result.scores.items(), key=lambda kv: -kv[1])[:3]:
            print(f"   {label:12} {p:6.3f}")
        if text_label:
            print(f"   consistency with text: {result.text_consistency}")
            print(f"   cross-modal conflict:  {result.cross_modal_conflict}")
            override = vision_service.image_type_override(text_label, result)
            if override:
                print(f"   text unclassified -> report type would become: {override}")
        phash = vision_service.compute_phash(image)
        for other_name, other_hash in hashes:
            distance = phash_distance(phash, other_hash)
            if distance <= settings.VISION_PHASH_MAX_DISTANCE:
                print(f"   near-duplicate of {other_name} ({distance} bits apart)")
        hashes.append((path.name, phash))
        print()


if __name__ == "__main__":
    main()
