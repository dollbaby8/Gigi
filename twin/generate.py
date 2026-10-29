"""Generate Instagram photos of your digital twin.

Usage:
    python -m twin.generate --list
    python -m twin.generate --preset courthouse_chic
    python -m twin.generate --preset all --num 2
    python -m twin.generate --prompt "at a Houston Astros game in a jersey, cheering"
"""
import argparse
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

import fal_client
from dotenv import load_dotenv

from twin.prompts import PRESETS, build_prompt

ROOT = Path(__file__).resolve().parent.parent
TWIN_FILE = ROOT / "twin.json"
OUTPUTS = ROOT / "outputs"

# Instagram-native sizes
SIZES = {
    "portrait": {"width": 1080, "height": 1350},  # 4:5 feed (best reach)
    "square": {"width": 1080, "height": 1080},
    "story": {"width": 1080, "height": 1920},  # 9:16 stories/reels
}


def generate(prompt: str, lora_url: str, size: str, num: int, scale: float, seed):
    args = {
        "prompt": prompt,
        "loras": [{"path": lora_url, "scale": scale}],
        "image_size": SIZES[size],
        "num_images": num,
        "num_inference_steps": 28,
        "guidance_scale": 3.5,  # lower = more natural, less "AI plastic"
        "output_format": "jpeg",
        "enable_safety_checker": True,
    }
    if seed is not None:
        args["seed"] = seed
    endpoint = os.getenv("FAL_GEN_ENDPOINT", "fal-ai/flux-lora")
    return fal_client.subscribe(endpoint, arguments=args)


def save(images, label: str) -> list[Path]:
    OUTPUTS.mkdir(exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    paths = []
    for i, img in enumerate(images):
        dest = OUTPUTS / f"{stamp}_{label}_{i}.jpg"
        urllib.request.urlretrieve(img["url"], dest)
        paths.append(dest)
    return paths


def main():
    load_dotenv(ROOT / ".env")
    ap = argparse.ArgumentParser()
    ap.add_argument("--preset", help="Preset name, or 'all'")
    ap.add_argument("--prompt", help="Custom scene (trigger word is added automatically)")
    ap.add_argument("--size", choices=SIZES, default="portrait")
    ap.add_argument("--num", type=int, default=4, help="Images per prompt (1-4)")
    ap.add_argument("--scale", type=float, default=1.0, help="Likeness strength (0.8-1.2)")
    ap.add_argument("--seed", type=int)
    ap.add_argument("--list", action="store_true", help="List presets")
    args = ap.parse_args()

    if args.list:
        for name in PRESETS:
            print(name)
        return
    if not os.getenv("FAL_KEY"):
        sys.exit("FAL_KEY is not set. Copy .env.example to .env and add your key.")
    if not TWIN_FILE.exists():
        sys.exit("No twin.json yet. Run: python -m twin.train")
    if not (args.preset or args.prompt):
        sys.exit("Pass --preset NAME, --preset all, or --prompt '...'")

    twin = json.loads(TWIN_FILE.read_text())
    trigger = twin["trigger_word"]

    if args.prompt:
        jobs = [("custom", args.prompt)]
    elif args.preset == "all":
        jobs = list(PRESETS.items())
    elif args.preset in PRESETS:
        jobs = [(args.preset, PRESETS[args.preset])]
    else:
        sys.exit(f"Unknown preset '{args.preset}'. Use --list.")

    for label, scene in jobs:
        prompt = build_prompt(scene, trigger)
        print(f"[{label}] generating {args.num}...")
        result = generate(prompt, twin["lora_url"], args.size, args.num, args.scale, args.seed)
        for p in save(result["images"], label):
            print("  saved", p.relative_to(ROOT))
        print(f"  seed: {result.get('seed')}  (reuse with --seed to iterate on a look)")


if __name__ == "__main__":
    main()
