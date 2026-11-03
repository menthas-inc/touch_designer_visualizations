# CLAUDE.md

> Keep this file lean. If removing a line would not cause a mistake, remove it.
> This file is *passive context*. Enforced rules live in `docs/constitution/principles.md`.

## Project

Live visuals for our studio, built in TouchDesigner. The network loads source videos, adjusts
them, and projects them on four tall strips of paper that are mapped in the file.

The `.toe` is a compressed binary. Nobody can read or diff it, so **the unit of change is a
Python script in `td/`**, run inside TouchDesigner, and committed. The network is read through a
dump script that writes every operator, its parameters and its wiring to a text file in `td/`,
which is what gets read and reviewed here. `docs/tech/setup.md` says how the loop runs.

Status: TouchDesigner is not installed yet and the `.toe` is still being downloaded. Nothing in
`td/` exists until both are here.

## How to work with me in this repo

- Be concise and direct. Surface real fork-in-the-road decisions, make the trivial calls yourself.
- Short, friendly, to the point. Not emphatic, not apologetic. No restating what I just said, no
  preamble, no summarising work I can read in the diff.
- Smallest-change discipline comes from the user-level `ponytail` plugin, always on, subagents
  included. Don't restate its rules in commands or agents; cite DEV-1 where the gate applies.
- When code and spec disagree, the spec wins. Update the code, or flag the spec as wrong.
- **Never invent a fact about the room.** Projector count and resolution, strip sizes, the
  mapping, what the source material is: those come from me or from the dump.
- No em dashes anywhere: comments, docs, commit messages. The pre-commit gate blocks them.

## Where things live

- TouchDesigner scripts and network dumps: `td/`
- Product and technical specs: `docs/specs/NNN-feature-slug/` (feature-spec, impl-spec, tasks)
- Enforced principles, the gate: `docs/constitution/principles.md`
- Technical decisions, and the open ones: `docs/tech/decisions.md`
- Workflows: `.claude/commands/` and `/plan-feature`, `/implement`, `/tweak`, `/review`
- Reviewer personas: `.claude/agents/`
- Mechanical gates: `.claude/hooks/` (secrets, pre-commit em-dash check and tests)

## Model defaults

- Session model is chosen at launch and switched freely with `/model`. Opus for cross-cutting
  work, Sonnet for routine implementation.
- Subagents are pinned in their own definitions. Do not override casually.
