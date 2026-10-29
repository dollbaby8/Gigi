# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Python CLI that builds a personal AI "digital twin" on fal.ai: it trains a FLUX LoRA on the owner's photos, then generates realistic Instagram photos.

## Commands

```bash
pip install -r requirements.txt
python -m twin.train --trigger GIGI [--steps N]        # zips photos/, trains, writes twin.json
python -m twin.generate --list                          # list presets
python -m twin.generate --preset NAME|all [--size portrait|square|story] [--num N] [--scale F] [--seed N]
python -m twin.generate --prompt "custom scene"
```

There are no tests or lint config yet.

## Architecture

- `twin/train.py`: zips `photos/`, uploads it with `fal_client.upload_file`, calls `FAL_TRAIN_ENDPOINT` (default `fal-ai/flux-lora-fast-training`), and saves the trigger word and LoRA URL to `twin.json`.
- `twin/generate.py`: reads `twin.json`, builds a prompt via `twin/prompts.py`, calls `FAL_GEN_ENDPOINT` (default `fal-ai/flux-lora`), and downloads the results to `outputs/`.
- `twin/prompts.py`: holds the scene presets (`{T}` is the trigger-word placeholder) and the shared `REALISM` suffix that is appended to every prompt.

## Conventions

- `FAL_KEY` lives in `.env` (gitignored).
- `photos/`, `outputs/`, and `twin.json` hold the owner's likeness and are gitignored. Never commit them.
- Run scripts as modules (`python -m twin.x`) from the repo root.
