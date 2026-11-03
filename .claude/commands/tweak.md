---
description: Make a small adjustment to a feature and keep its specs in sync.
argument-hint: <what to change> (optionally: NNN-slug)
---
Small change: **$ARGUMENTS**

This is a minor adjustment, not a re-plan. Do not spin up the planning agents.

1. Locate the affected feature folder in `docs/specs/`. Ask if it is unclear which one.
2. Make the smallest change that achieves it (DEV-1), as a committed script in `td/` if it
   touches the network (SV-1).
3. **Spec sync, required.** Update the affected feature-spec.md, impl-spec.md and tasks.md so
   they still describe reality (DEV-2). If the tweak changes behaviour or acceptance criteria,
   that edit is part of this task and is not optional.
4. Run the tests. Add or adjust tests if the change alters covered behaviour (QUAL-1).

If this turns out to be a major change (a new source pipeline, a new output, a remap), stop and
tell me. It should go through `/plan-feature` instead.
