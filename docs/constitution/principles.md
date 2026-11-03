# Principles

> Format: each principle has an ID, a level (MUST = hard gate, SHOULD = strong default), and a
> one-line rationale.
> Keep these few and real. A constitution that lists everything enforces nothing.
>
> These are enforced. Passive context lives in `CLAUDE.md`; the stack lives in `docs/tech/`.
>
> **The SV section is DRAFT.** It was written before the file was opened. Confirm, cut or add.

## Development (DEV)

- **DEV-1 (MUST):** The smallest change that satisfies the spec. No speculative abstraction or
  unused extensibility.
- **DEV-2 (MUST):** Code matches its spec. If they diverge, fix the code or amend the spec in the
  same change, never silently.
- **DEV-3 (SHOULD):** Prefer boring, well-understood tools over novel ones unless the spec
  justifies otherwise.

## Quality (QUAL)

- **QUAL-1 (MUST):** No feature merges without tests covering its acceptance criteria.
- **QUAL-2 (SHOULD):** Functions do one thing; side effects are explicit and isolated.

## Studio visuals (SV)

- **SV-1 (MUST): Every change to the network is reproducible from a committed script.** The
  `.toe` is binary and cannot be diffed, reviewed or merged. A change made by hand in the editor
  with nothing checked in is lost the first time the file is restored. Rationale: the script is
  the only history this project has.

- **SV-2 (MUST): Calibration is real-hardware data and is never guessed or overwritten.** The
  mapping of the four strips was measured in the room. A script that touches those values does
  so only when that is its stated purpose, and the previous values are kept. Rationale: redoing
  the mapping costs an evening with the projectors on.

- **SV-3 (SHOULD): It has to hold frame rate on the show machine.** A change that adds per-frame
  cost says so, and says what it costs. Rationale: a dropped frame is visible on a wall.
