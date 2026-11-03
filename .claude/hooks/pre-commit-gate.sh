#!/usr/bin/env bash
# PreToolUse hook for Bash. If the command is a `git commit`, run the project's
# test and lint gate and block the commit (exit 2) on failure. QUAL-1.
set -euo pipefail
payload="$(cat)"
cmd="$(printf '%s' "$payload" | grep -oE '"command"\s*:\s*"[^"]*"' | head -1 || true)"

case "$cmd" in
  *"git commit"*)
    cd "${CLAUDE_PROJECT_DIR:-.}"

    # Em dashes are a copy rule and this is the only gate that sees every file
    # however it was written, including through a shell heredoc.
    emdash="$(printf '\xe2\x80\x94')"
    offenders=""
    while IFS= read -r f; do
      case "$f" in
        *.lock|pnpm-lock.yaml|package-lock.json|yarn.lock) continue ;;
      esac
      [ -f "$f" ] || continue
      if grep -qF "$emdash" "$f" 2>/dev/null; then offenders="$offenders $f"; fi
    done <<< "$(git diff --cached --name-only --diff-filter=ACM 2>/dev/null)"
    if [ -n "$offenders" ]; then
      echo "BLOCKED by pre-commit gate: em dash found in:$offenders" >&2
      echo "Use a comma, a colon or a full stop instead." >&2
      exit 2
    fi

    # Package manager follows the lockfile, so this keeps working once the stack lands.
    PM=""
    if [ -f pnpm-lock.yaml ]; then PM="pnpm"
    elif [ -f yarn.lock ]; then PM="yarn"
    elif [ -f bun.lock ] || [ -f bun.lockb ]; then PM="bun"
    elif [ -f package-lock.json ]; then PM="npm run"
    fi

    TEST_CMD="${PROJECT_TEST_CMD:-}"
    LINT_CMD="${PROJECT_LINT_CMD:-}"
    # Only fall back to package scripts once dependencies are actually installed,
    # otherwise a fresh clone cannot make its first commit.
    if [ -n "$PM" ] && [ -d node_modules ]; then
      if [ -z "$TEST_CMD" ] && grep -q '"test"' package.json 2>/dev/null; then TEST_CMD="$PM test"; fi
      if [ -z "$LINT_CMD" ] && grep -q '"lint"' package.json 2>/dev/null; then LINT_CMD="$PM lint"; fi
    fi
    if [ -n "$TEST_CMD" ]; then
      echo "pre-commit gate: running $TEST_CMD" >&2
      if ! eval "$TEST_CMD" >&2; then
        echo "BLOCKED by pre-commit gate: tests failed (QUAL-1). Fix before committing." >&2
        exit 2
      fi
    fi
    if [ -n "$LINT_CMD" ]; then
      if ! eval "$LINT_CMD" >&2; then
        echo "BLOCKED by pre-commit gate: lint failed." >&2
        exit 2
      fi
    fi
    ;;
esac
exit 0
