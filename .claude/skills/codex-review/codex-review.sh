#!/usr/bin/env bash
# Codex review wrapper
#
# Handles a CLI quirk: `codex review` scope flags (--uncommitted, --base, --commit)
# and [PROMPT] are mutually exclusive. When both are needed, this wrapper uses
# `codex exec -s read-only` agent mode, which can run git commands to get context.
#
# Usage:
#   codex-review.sh --uncommitted                          # Default review of uncommitted changes
#   codex-review.sh --base main                            # Default review against main
#   codex-review.sh --uncommitted "Focus on security"      # Custom review of uncommitted changes
#   codex-review.sh --base main -m o3 "Check race conditions"  # Custom model + instructions
#   codex-review.sh --commit abc123 "Check for regressions"
#   codex-review.sh -o /tmp/review.md --base main          # Custom output path

set -eo pipefail

SCOPE_TYPE=""
SCOPE_VALUE=""
MODEL=""
OUTPUT_FILE=""
INSTRUCTIONS=""
TITLE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --uncommitted) SCOPE_TYPE="uncommitted"; shift ;;
    --base) SCOPE_TYPE="base"; SCOPE_VALUE="$2"; shift 2 ;;
    --commit) SCOPE_TYPE="commit"; SCOPE_VALUE="$2"; shift 2 ;;
    --model|-m) MODEL="$2"; shift 2 ;;
    --output|-o) OUTPUT_FILE="$2"; shift 2 ;;
    --title) TITLE="$2"; shift 2 ;;
    --help|-h)
      echo "Usage: codex-review.sh [OPTIONS] [INSTRUCTIONS...]"
      echo ""
      echo "Scope (pick one):"
      echo "  --uncommitted         Review staged, unstaged, and untracked changes"
      echo "  --base BRANCH         Review changes against base branch"
      echo "  --commit SHA          Review a specific commit"
      echo ""
      echo "Options:"
      echo "  --model, -m MODEL     Model to use (default: codex CLI default)"
      echo "  --output, -o FILE     Output file (default: /tmp/codex-review-TIMESTAMP.md)"
      echo "  --title TITLE         Context title for the review"
      echo ""
      echo "Positional arguments after options are treated as custom review instructions."
      echo "When scope flags and instructions are both provided, uses codex exec agent mode."
      exit 0
      ;;
    --) shift; INSTRUCTIONS="$*"; break ;;
    -*) echo "Unknown option: $1" >&2; exit 1 ;;
    *) INSTRUCTIONS="$*"; break ;;
  esac
done

# Default output file
if [[ -z "$OUTPUT_FILE" ]]; then
  OUTPUT_FILE="/tmp/codex-review-$(date +%s).md"
fi

# Case 1: Scope + custom instructions → use exec agent mode
if [[ -n "$SCOPE_TYPE" && -n "$INSTRUCTIONS" ]]; then
  case "$SCOPE_TYPE" in
    uncommitted)
      GIT_CONTEXT="Run \`git diff\` and \`git diff --cached\` and \`git ls-files --others --exclude-standard\` to see all uncommitted changes (unstaged, staged, and untracked)."
      ;;
    base)
      GIT_CONTEXT="Run \`git diff ${SCOPE_VALUE}...HEAD\` to see all changes on this branch compared to ${SCOPE_VALUE}."
      ;;
    commit)
      GIT_CONTEXT="Run \`git show ${SCOPE_VALUE}\` to see the changes introduced by commit ${SCOPE_VALUE}."
      ;;
  esac

  TITLE_CONTEXT=""
  if [[ -n "$TITLE" ]]; then
    TITLE_CONTEXT=" The change is titled: \"${TITLE}\"."
  fi

  FULL_PROMPT="You are performing a code review.${TITLE_CONTEXT} ${GIT_CONTEXT} Then review the changes with these instructions: ${INSTRUCTIONS}. Output your findings as markdown with severity levels (critical/high/medium/low) and file:line references."

  echo "==> Using codex exec mode (scope + custom instructions)" >&2
  echo "==> Output: ${OUTPUT_FILE}" >&2
  echo "" >&2

  # Build command
  CMD=(codex exec -s read-only)
  [[ -n "$MODEL" ]] && CMD+=(-m "$MODEL")
  CMD+=(-o "$OUTPUT_FILE" "$FULL_PROMPT")

  "${CMD[@]}"

  echo "" >&2
  echo "==> Review saved to: ${OUTPUT_FILE}" >&2

# Case 2: Scope only → use native review mode
elif [[ -n "$SCOPE_TYPE" ]]; then
  echo "==> Using codex review mode" >&2
  echo "==> Output: ${OUTPUT_FILE}" >&2
  echo "" >&2

  # Build command
  CMD=(codex review)
  [[ -n "$MODEL" ]] && CMD+=(-m "$MODEL")
  case "$SCOPE_TYPE" in
    uncommitted) CMD+=(--uncommitted) ;;
    base) CMD+=(--base "$SCOPE_VALUE") ;;
    commit) CMD+=(--commit "$SCOPE_VALUE") ;;
  esac
  [[ -n "$TITLE" ]] && CMD+=(--title "$TITLE")

  "${CMD[@]}" 2>&1 | tee "$OUTPUT_FILE"

  echo "" >&2
  echo "==> Review saved to: ${OUTPUT_FILE}" >&2

# Case 3: Instructions only → use native review mode with prompt
elif [[ -n "$INSTRUCTIONS" ]]; then
  echo "==> Using codex review mode with custom prompt" >&2
  echo "==> Output: ${OUTPUT_FILE}" >&2
  echo "" >&2

  # Build command
  CMD=(codex review)
  [[ -n "$MODEL" ]] && CMD+=(-m "$MODEL")
  CMD+=("$INSTRUCTIONS")

  "${CMD[@]}" 2>&1 | tee "$OUTPUT_FILE"

  echo "" >&2
  echo "==> Review saved to: ${OUTPUT_FILE}" >&2

# Case 4: Nothing provided
else
  echo "Error: Provide a scope flag (--uncommitted, --base, --commit) and/or custom instructions." >&2
  echo "Run with --help for usage." >&2
  exit 1
fi
