"""Train a personal LoRA "digital twin" on fal.ai from the photos in ./photos.

Usage:
    python -m twin.train                       # defaults
    python -m twin.train --trigger GIGI --steps 1500
"""
import argparse
import json
import os
import sys
import tempfile
import zipfile
from pathlib import Path

import fal_client
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
PHOTOS = ROOT / "photos"
TWIN_FILE = ROOT / "twin.json"
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def collect_photos() -> list[Path]:
    photos = sorted(p for p in PHOTOS.iterdir() if p.suffix.lower() in IMAGE_EXTS)
    if len(photos) < 10:
        sys.exit(f"Found {len(photos)} photos in {PHOTOS}. Add at least 10 (15-25 is ideal).")
    if len(photos) > 40:
        print(f"Note: {len(photos)} photos - more isn't better past ~30; cull blurry/filtered ones.")
    return photos


def zip_photos(photos: list[Path]) -> Path:
    out = Path(tempfile.mkdtemp()) / "training_photos.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for i, p in enumerate(photos):
            zf.write(p, f"{i:03d}{p.suffix.lower()}")
    return out


def log_updates(update):
    if isinstance(update, fal_client.InProgress):
        for entry in update.logs or []:
            print("  ", entry["message"])


def main():
    load_dotenv(ROOT / ".env")
    if not os.getenv("FAL_KEY"):
        sys.exit("FAL_KEY is not set. Copy .env.example to .env and add your key.")

    ap = argparse.ArgumentParser()
    ap.add_argument("--trigger", default="GIGI", help="Unique word that summons your face in prompts")
    ap.add_argument("--steps", type=int, default=1000, help="Training steps (1000-2000 typical)")
    args = ap.parse_args()

    endpoint = os.getenv("FAL_TRAIN_ENDPOINT", "fal-ai/flux-lora-fast-training")
    photos = collect_photos()
    print(f"Zipping {len(photos)} photos...")
    archive = zip_photos(photos)

    print("Uploading to fal storage...")
    images_url = fal_client.upload_file(str(archive))

    print(f"Training on {endpoint} (usually 5-15 min)...")
    result = fal_client.subscribe(
        endpoint,
        arguments={
            "images_data_url": images_url,
            "trigger_word": args.trigger,
            "steps": args.steps,
            "create_masks": True,  # focuses training on the face/person
            "is_style": False,
        },
        with_logs=True,
        on_queue_update=log_updates,
    )

    twin = {
        "trigger_word": args.trigger,
        "lora_url": result["diffusers_lora_file"]["url"],
        "config_url": result.get("config_file", {}).get("url"),
        "train_endpoint": endpoint,
        "steps": args.steps,
        "photo_count": len(photos),
    }
    TWIN_FILE.write_text(json.dumps(twin, indent=2))
    print(f"\nDone. Twin saved to {TWIN_FILE}")
    print(f"Next: python -m twin.generate --preset river_oaks_brunch")


if __name__ == "__main__":
    main()
