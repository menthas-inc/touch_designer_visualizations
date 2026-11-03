---
description: Implement a planned feature from its spec artifacts.
argument-hint: <NNN-slug>
---
Implement the feature in `docs/specs/$ARGUMENTS/`. Read feature-spec.md, impl-spec.md and
tasks.md first.

## Approach
1. Use the `explorer` agent to gather the relevant context rather than reading broadly in this
   session, including the operators in the latest network dump.
2. Work tasks.md in order. For each task:
   - Implement the smallest change that satisfies it (DEV-1).
   - Keep the code aligned to the impl-spec. If reality forces a divergence, update the spec in
     the same step (DEV-2).
   - Mark the task `[~]` then `[x]` in tasks.md as you go.
3. After each phase, run the tests and fix failures before moving on.
4. Before declaring done, run `code-reviewer` on the full diff.

## While you build
- Every change to the network is a script in `td/`, committed. Nothing is edited by hand in
  TouchDesigner without the script that reproduces it (SV-1).
- Never touch the mapping or calibration values unless the task is about them (SV-2).
- No em dashes anywhere, including comments and commit messages.

Stop and ask if the spec is ambiguous or an edge case is not covered. Do not invent product
behaviour, and never invent a fact about the room, the projectors or the material: those come
from me.

End with: tasks completed, test status, and open review findings.
