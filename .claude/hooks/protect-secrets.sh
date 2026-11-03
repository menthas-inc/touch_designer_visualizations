#!/usr/bin/env bash
# PreToolUse hook for Bash. Blocks (exit 2) any command that would clobber a
# file holding credentials that exist nowhere else.
#
# Why this exists: .env was overwritten with a truncating redirect during
# setup, taking a Google client secret, Apple key material and a Resend key
# with it. .env is gitignored, correctly, so there was nothing to restore from
# and no snapshot held a copy. "Read before you overwrite" is a good intention;
# this is the control.
#
# Two false positives were found while writing it, and both are handled,
# because a safety check that cries wolf is a safety check somebody turns off:
#
#   1. It matches the TARGET of an operation, not a filename appearing anywhere
#      in the command. Writing an unrelated file whose body mentions .env is fine.
#   2. Heredoc bodies are stripped before matching. A script being written out
#      may legitimately contain the text "cat > .env" as data.
#
#   blocked:  cat > .env      rm .env      mv x .env      cat > ~/.ssh/id_rsa
#   allowed:  cat >> .env     cat .env     cat > other.ts (whatever the body says)
set -uo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
payload="$(cat)"

command -v python3 >/dev/null 2>&1 || exit 0
cmd="$(printf '%s' "$payload" | python3 "$here/_extract.py" command 2>/dev/null)"
[ -n "$cmd" ] || exit 0

verdict="$(
  CMD="$cmd" python3 - <<'PY'
import os, re, sys

cmd = os.environ.get("CMD", "")

# Strip heredoc bodies. Everything between `<<DELIM` and a line that is just
# DELIM is data being written, not commands being run, so shell-looking text
# inside it must not trip the check.
def strip_heredocs(text: str) -> str:
    out, lines, i = [], text.split("\n"), 0
    while i < len(lines):
        line = lines[i]
        out.append(line)
        opener = re.search(r"<<-?\s*[\"']?([A-Za-z_][A-Za-z0-9_]*)[\"']?", line)
        if opener:
            delim = opener.group(1)
            i += 1
            while i < len(lines) and lines[i].strip() != delim:
                i += 1
        i += 1
    return "\n".join(out)

cmd = strip_heredocs(cmd)

PROTECTED = re.compile(r"(^|/)(\.env(\.[A-Za-z0-9_-]+)?|id_ed25519|id_rsa|id_ecdsa)$|\.p8$")

def protected(path: str) -> bool:
    path = path.strip().strip("\"'")
    if not path:
        return False
    # Committed templates hold placeholders, not secrets.
    if path.endswith((".env.example", ".env.sample")):
        return False
    return bool(PROTECTED.search(path))

# A single '>' (never '>>') whose target is a protected path.
for match in re.finditer(r"(?<!>)>(?!>)\s*([^\s;&|<>]+)", cmd):
    if protected(match.group(1)):
        print("clobber"); sys.exit(0)

# rm / mv / truncate / shred naming a protected path as an operand.
for segment in re.split(r"[;&|\n]+", cmd):
    words = segment.split()
    if not words:
        continue
    verb = os.path.basename(words[0])
    if verb in {"rm", "mv", "truncate", "shred"}:
        for word in words[1:]:
            if not word.startswith("-") and protected(word):
                print("remove"); sys.exit(0)

print("ok")
PY
)"

if [ "$verdict" != "ok" ]; then
  echo "BLOCKED: this would overwrite or remove a file holding credentials that exist nowhere else." >&2
  echo "  .env and key files are gitignored, so there is no version to restore from." >&2
  echo "  Read it first, then append with >> or edit the one line that needs changing." >&2
  exit 2
fi
exit 0
