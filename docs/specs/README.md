# Specs

One folder per feature: `docs/specs/NNN-feature-slug/`, zero-padded and monotonically increasing.

Each folder holds three artifacts, produced in order by `/plan-feature`:

1. **feature-spec.md**, the *what* and *why*. Product-level. No tech choices.
2. **impl-spec.md**, the *how*. Which operators change, the script that changes them, data flow,
   dependencies, edge cases, and which principles apply.
3. **tasks.md**, ordered testable tasks an agent can execute, each citing the acceptance criteria
   it satisfies.

`/implement` consumes all three. `/tweak` updates them in place for a small change.

## Conventions

- Acceptance criteria are numbered `AC-1`, `AC-2` and are testable. If you cannot write a test
  for it, it is too vague.
- Every task cites the AC it serves.
- Anything that touches the mapping says so in its own section (SV-2).
