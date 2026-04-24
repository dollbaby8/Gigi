# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

There is no source code in the repo yet. Until that changes, this file is the project charter — what Gigi is meant to become, what the user wants out of it, and the rails future sessions should stay on. As real code lands, update the sections below to describe the code that exists, not the intent.

## What Gigi is

Gigi is a personal assistant agent system the user runs from their Mac mini (their always-on machine, though they own several Macs). Architecturally it is one **main orchestrator agent** that routes requests to a small set of **subagents**, each focused on one area of the user's life.

Subagents, in priority order:

- **Stylist** — outfit and style suggestions. Accepts photos of the user's wardrobe and suggests combinations, seasonal refreshes, and what to buy.
- **Dating coach** — situation-specific advice, and *drafts* of messages the user can send. The agent does not send anything itself; drafts go to the user for review.
- **Deal hunter** — watches the user's preferred clothing and beauty sites for sales, price drops, and back-in-stock events. Reports through async notifications (see *Interfaces*).
- **Side-income explorer** *(placeholder)* — the user wants an agent that helps them earn on the side but has not chosen an angle yet. Leave this sketched but unbuilt. Ask the user before designing anything concrete here.

## What Gigi is NOT

- Not an email / calendar / to-do replacement. The user keeps reminders and todos by hand in a paper notebook on purpose — do not propose automating that.
- Not an autonomous sender. No agent sends messages, DMs, or posts on the user's behalf without an explicit human-in-the-loop confirmation step.

## Runtime

- **Host**: the user's Mac mini, which stays on 24/7. No cloud hosting — the user is not comfortable operating cloud infrastructure, and the Mac mini is effectively the "server."
- **Scheduling**: use `launchd` (macOS native) for background wakeups. Prefer periodic runs (every 15–60 min for background agents, daily for briefings) over always-on loops; tight loops burn API budget.
- **Interaction surfaces** the user has asked for:
  1. A `gigi` terminal command for interactive chat from any Mac.
  2. A **Raycast** hotkey for quick one-shot requests from anywhere on the Mac. Use Raycast **Script Commands** (simple shell/Python scripts with a header) rather than a full extension unless there is a real reason.
  3. **iMessage / SMS** push for async notifications from background agents (e.g. deal alerts). Use AppleScript via `osascript` to send from the Messages app on the Mac mini. The user will need to grant Automation permission.

## Stack

- **Language**: Python 3.
- **Model provider**: Anthropic (Claude) via the official `anthropic` Python SDK.
- **Default model**: Claude Haiku 4.5 (`claude-haiku-4-5-20251001`). Use for routing, short chats, deal scanning, and anything straightforward.
- **Upgrade model**: Claude Sonnet 4.6 (`claude-sonnet-4-6`). Use for longer drafts, outfit analysis with vision, and harder reasoning. Do not reach for Opus by default.
- **Prompt caching**: turn it on for every long or reused system prompt and tool schema. The budget below depends on it.

## Budget and cost discipline

The user's target is **$20–50 / month** on Claude API usage. Every design choice should respect that:

- Haiku first. Only escalate to Sonnet when Haiku output is measurably worse for the task.
- Apply `cache_control` to system prompts, tool definitions, and any long reusable context.
- Scheduled wakeups over always-on loops.
- Short context per background run — pass only the fields the agent needs, not rolling chat history.

## User profile

- **Comfort level**: can follow written instructions and copy/paste commands, not a fluent coder. Claude Code should do the file edits; the user reviews. Write exact commands and file paths — no handwaving.
- **Old-school by choice**: journals, todos, and reminders stay on paper. Do not propose digital replacements.
- **Platform**: macOS only. Assume `brew`, `launchd`, and Raycast are available. Do not propose Linux-only or Windows-only tooling.

## Conventions (for when code lands)

- Each subagent lives in its own directory under `agents/` (e.g. `agents/stylist/`, `agents/deal_hunter/`).
- Each subagent exposes a single entry-point function: takes structured input, returns a structured result. `launchd` wrappers live in `launchd/`.
- Shared code — Anthropic client setup, caching helpers, iMessage sender, Raycast output formatting — lives in `lib/`.
- Configuration in `config.toml`. Secrets in `.env` (never commit; ship `.env.example`).
- When adding a subagent, update the *Subagents* list above so the charter stays current.

## First build steps

When the user is ready to start coding, scaffold in this order:

1. `pyproject.toml`, `.env.example`, `config.toml`, `.gitignore`.
2. `lib/claude.py` — thin wrapper around the Anthropic SDK that applies prompt caching by default and picks Haiku vs. Sonnet based on a `tier` argument.
3. `gigi` CLI — minimal interactive chat against the orchestrator prompt, running on Haiku.
4. First subagent: **Stylist** (the user ranked fashion + shopping research highest).
5. `launchd` plist + iMessage sender, then wire up **Deal hunter** as the first scheduled agent.

Do not build Dating coach or Side-income explorer until the above is working end to end.

## Working branch

Per the task configuration, development happens on `claude/setup-claudine-config-woy5k`. Commit and push work to that branch.
