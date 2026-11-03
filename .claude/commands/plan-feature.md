---
description: Plan a feature end to end. Spec, review, constitution gate, impl-spec and tasks.
argument-hint: <feature description>
---
Plan the feature: **$ARGUMENTS**

Work through these phases. Pause for my input where noted.

## 1. Feature spec, the what and why
Read `docs/specs/README.md` for the format and pick the next NNN. Read the latest network dump in
`td/` so the spec describes the network that exists, not an imagined one.

Draft `docs/specs/NNN-slug/feature-spec.md`: why, what, acceptance criteria (AC-n, testable),
out of scope. No tech choices yet.

## 2. Clarify
Identify ambiguities and edge cases. Ask me the open questions in one batch. Fold the answers
into the spec.

## 3. Review
Run `project-lead` on the feature-spec: product coherence, operability, complexity. Synthesize
and revise. Report what you changed and what you deliberately did not.

## 4. Constitution gate
Audit the revised feature-spec yourself against every principle in
`docs/constitution/principles.md`, read fresh. For each relevant principle state compliant,
violated or not-applicable, with one line of evidence. A violated MUST is CRITICAL and blocks.
A violated SHOULD is a flag needing a stated justification.

End the phase with a single line: `GATE: PASS` or `GATE: BLOCKED (open MUST violations: <ids>)`.
Do not continue while a MUST is open.

## 5. Impl-spec, the how
Write `docs/specs/NNN-slug/impl-spec.md`: which operators change, the script that makes the
change, data flow, dependencies, edge cases, and a constitution check saying which principles
apply and how they are satisfied. Ground every choice in `docs/tech/`. If the feature depends on
one of the open decisions at the bottom of `docs/tech/decisions.md`, say so rather than assuming
an answer.

Design it the ponytail way. Run every new piece (operator chain, script, dependency, config) down
the `ponytail` ladder and stop at the first rung that holds: not needed, already in the network,
TouchDesigner or the palette does it, an installed dependency, new code. Add a short **Reuse and
skips** section: each new piece with its rung, then what you deliberately left out. A limit you
knowingly accept names its upgrade trigger, and the code for it will carry a `shortcut:` comment.

Then run `project-lead` on the impl-spec as the tech lead review. Fold its concerns into the spec,
or say why not.

## 6. Tasks
Write `docs/specs/NNN-slug/tasks.md`: ordered testable tasks (setup, foundational, feature,
tests), each citing the acceptance criteria and principles it satisfies.

End by listing the three artifact paths and any unresolved SHOULD-level flags.
