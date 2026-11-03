#!/usr/bin/env bash
# PreToolUse hook for Write|Edit|MultiEdit. Blocks (exit 2) if the content being
# written looks like a secret. Reads the tool-call JSON on stdin. SEC-1.
set -uo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
payload="$(cat)"

if command -v python3 >/dev/null 2>&1; then
  path="$(printf '%s' "$payload" | python3 "$here/_extract.py" path)"
else
  path=""
fi

# Example and template files are meant to carry placeholder shapes.
case "$path" in
  *.example|*.example.*|*.sample|*/docs/*) exit 0 ;;
esac

if command -v python3 >/dev/null 2>&1; then
  content="$(printf '%s' "$payload" | python3 "$here/_extract.py" content)"
else
  # Fallback: scan the raw payload. Noisier, but it never silently misses.
  content="$payload"
fi

[ -n "$content" ] || exit 0

# High-signal secret patterns. Tune as the stack grows.
patterns='(AKIA[0-9A-Z]{16})|(-----BEGIN [A-Z ]*PRIVATE KEY-----)|(sk-ant-[A-Za-z0-9_-]{20,})|(sk-[A-Za-z0-9]{20,})|(ghp_[A-Za-z0-9]{36})|(xox[baprs]-[A-Za-z0-9-]+)|(postgres(ql)?://[^:@ ]+:[^@ ]{6,}@)|((password|passwd|secret|api[_-]?key|access[_-]?key|auth[_-]?token|client[_-]?secret)[[:space:]]*[:=][[:space:]]*.?[A-Za-z0-9/+_-]{12,})'

# Drop lines whose value is obviously a placeholder before matching.
content="$(printf '%s' "$content" | grep -viE '(your[-_]|<[a-z_]+>|changeme|placeholder|xxxx|\.\.\.|example\.com)' || true)"

if printf '%s' "$content" | grep -qiE "$patterns"; then
  echo "BLOCKED by secret-scan: the write appears to contain a secret (SEC-1). Move it to env or secret storage." >&2
  exit 2
fi
exit 0
