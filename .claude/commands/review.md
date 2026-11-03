---
description: On-demand deep review. Bugs, performance, and constitution adherence.
argument-hint: [scope: diff | path | feature NNN-slug] (default: uncommitted diff)
---
Deep review of: **$ARGUMENTS** (default: the current uncommitted diff).

Run `code-reviewer` (ponytail-review: bugs, scale, tests, speed, lean). Do not review inline
yourself.

Then do the constitution pass yourself: audit the change against every principle in
`docs/constitution/principles.md`, read fresh. For each relevant principle, state compliant,
violated or not-applicable with one line of evidence.

Merge everything into one report, deduplicated, ordered by severity (CRITICAL to LOW). For each
finding: `file:line`, the issue, the principle or AC it touches, and a concrete fix. End with a
single line: `GATE: PASS` or `GATE: BLOCKED (open MUST violations: <ids>)`.

Do not fix anything unless I ask.
