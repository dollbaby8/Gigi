# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Status

This repository (`dollbaby8/Gigi`) contains no source code yet. The only tracked file is this `CLAUDE.md` (added in commit `5548b1d`, "Add initial CLAUDE.md placeholder"). There is no `main` branch on the remote — the only branches that exist are the `claude/add-claude-documentation-*` working branches used to seed this documentation. There is no build system, no test runner, no linter, no package manifest, and no application entry point to describe.

When source code lands, update this file with:

- **Build / test / lint commands** — the exact invocations, including how to run a single test.
- **Architecture overview** — the cross-file structure and data flow that is not obvious from reading any single file.
- **Project-specific conventions** — anything non-obvious about how code in this repo is organized, named, or wired together.

Until that content exists, there is nothing repo-specific to document here. Do not invent commands, frameworks, or architecture; read the actual files that get added and update this file based on them.

## Working Branch

Development for the current documentation task happens on `claude/add-claude-documentation-64Znk`. Commit and push work to that branch. (An earlier task branch, `claude/add-claude-documentation-dGkHI`, also exists on the remote from a prior session.) Do not push to `main` — it does not exist yet, and the project has not established a default branch.

## Working With This Repo Before Code Exists

- Do not fabricate a `package.json`, `pyproject.toml`, `Makefile`, README, or similar scaffolding unless the user explicitly requests it. Adding speculative tooling commits the project to choices the owner has not made.
- If asked "how do I run tests / build this?", the honest answer is that there is nothing to run — say so rather than guessing a stack.
- When real source lands, replace this section wholesale; do not leave stale "empty repo" guidance alongside a populated codebase.
