# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Status

This repository (`dollbaby8/Gigi`) has no application source code, build configuration, or README yet. The only content is the Claude Code configuration under `.claude/`.

When source code lands, this file should be updated with:

- **Build / test / lint commands** — the exact invocations, including how to run a single test.
- **Architecture overview** — the cross-file structure and data flow that is not obvious from reading any single file.
- **Project-specific conventions** — anything non-obvious about how code in this repo is organized, named, or wired together.

Until that content exists, there is nothing repo-specific to document here. Do not invent commands or architecture; read the actual files that get added and update this file based on them.

## Installed Skills

`.claude/skills/prompt-master/` — vendored from [nidhinjs/prompt-master](https://github.com/nidhinjs/prompt-master) (MIT, v1.7.0). Generates optimized prompts for a target AI tool; triggers only on explicit prompt-writing requests, or via `/prompt-master`. `SKILL.md` loads `references/patterns.md` and `references/templates.md` on demand.

Because it is committed under `.claude/skills/`, it is available to anyone who clones this repo — no per-machine install step. Treat the files as vendored: to upgrade, re-copy from upstream rather than editing in place.
