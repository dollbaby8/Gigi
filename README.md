# Gigi — AI Digital Twin (fal.ai)

Trains a private FLUX LoRA on your photos, then generates realistic Instagram-ready shots of you.

## 1. Setup (one time)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # paste your key from https://fal.ai/dashboard/keys
```

## 2. Add your photos to `photos/`

15–25 photos give the best results. To get a twin that actually looks like you:

- **Mix of shots:** about 10 close-ups of your face, 6 from the waist up, and 4 full-body.
- **Variety:** different angles, outfits, lighting, backgrounds, and expressions.
- **Clean:** no filters, beauty mode, sunglasses, hats covering your face, or group shots.
- **Recent:** photos from the last 6–12 months, so it matches how you look now.
- **Sharp:** high resolution only. Blurry photos teach the model blur.

Photos are gitignored and are never committed.

## 3. Train your twin (~5–15 min, roughly $2–$5)

```bash
python -m twin.train --trigger GIGI
```

This writes `twin.json`, which holds your private LoRA URL. Keep it private.

## 4. Generate photos

```bash
python -m twin.generate --list                       # see scene presets
python -m twin.generate --preset river_oaks_brunch
python -m twin.generate --preset all --num 2         # a full content batch
python -m twin.generate --prompt "at a Houston Astros game in a jersey, cheering"
python -m twin.generate --preset date_night --size story
```

Images land in `outputs/`. Each image costs a few cents.

| Flag | Default | Notes |
|---|---|---|
| `--size` | `portrait` | `portrait` 4:5 (feed), `square`, `story` 9:16 |
| `--num` | 4 | Images per prompt |
| `--scale` | 1.0 | Raise to 1.1–1.2 if it doesn't look enough like you; lower if it looks stiff |
| `--seed` | random | Reuse a seed you liked to make variations of it |

## Realism tips

- Generate 4 and keep 1. Throw out anything with odd hands, teeth, or jewelry.
- Keep scenes believable: places you actually go, and outfits you'd actually wear.
- Edit lightly in Lightroom or VSCO so the AI shots match your real posts.
- Mix in real photos. A feed that's 100% AI starts to look uncanny.

## Instagram compliance

- **Meta AI label:** Meta requires you to disclose photorealistic AI content. Turn on the "AI info" label when you post.
- **FTC:** Sponsored posts need `#ad` or a paid-partnership tag. An AI-generated image doesn't change that.
