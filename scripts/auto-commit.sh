#!/usr/bin/env bash
# Auto commit & push hook for Claude Code Stop event.
# Runs from project root; never blocks the Stop event (always exits 0).

set +e
cd "$(dirname "$0")/.." || exit 0

LOG=".claude/auto-commit.log"
mkdir -p .claude

# Skip if there is nothing to commit (no tracked diff, no unstaged diff, no untracked).
if git diff --quiet && git diff --cached --quiet && [ -z "$(git ls-files --others --exclude-standard)" ]; then
  echo "[$(date -Iseconds)] no changes" >> "$LOG"
  exit 0
fi

{
  echo "[$(date -Iseconds)] staging changes"
  git add -A
  git commit -m "auto: $(date -Iseconds) via Claude Code"
  if git remote get-url origin >/dev/null 2>&1; then
    branch=$(git symbolic-ref --short HEAD 2>/dev/null || echo main)
    echo "[$(date -Iseconds)] pushing $branch (with tags)"
    git push --follow-tags origin "$branch" || echo "[$(date -Iseconds)] push failed (continuing)"
  else
    echo "[$(date -Iseconds)] no remote 'origin' configured — skipping push"
  fi
} >> "$LOG" 2>&1

exit 0
