---
name: codex-review
description: Invoke OpenAI Codex CLI for second-opinion code review, bug analysis, and security review. Use when you want a cross-check from a different AI model on code changes, debugging hypotheses, or security concerns.
user_invocable: true
---

# Codex Review Skill

## Purpose

Use Codex CLI as a complementary review tool. Different model architectures catch different bugs. This is for targeted second opinions, not blanket review of everything.

**Key Principle**: Evidence first, solutions second. Codex provides a fresh perspective, but evaluate findings critically.

---

## When to Use

- **After architect reviews code** - Cross-check complex implementations
- **During debugging** - Fresh perspective on root cause hypotheses
- **Security-sensitive code** - Authentication, authorization, input validation, data exposure
- **Complex algorithms** - Logic-heavy code, race conditions, edge cases
- **When something "feels off"** - Can't pinpoint the issue but intuition flags it
- **Pre-merge validation** - Final check before merging critical changes

**Don't use for**:
- Every commit (too noisy)
- Style/formatting issues (use linters)
- Trivial changes (single-line fixes)
- Documentation-only changes

**Context warning**: Codex output is verbose. Prefer launching a subagent (`general-purpose`) to run the wrapper script and return distilled findings.

---

## CLI Quirk: Scope vs Prompt Are Mutually Exclusive

**CRITICAL**: In `codex review`, scope flags (`--uncommitted`, `--base`, `--commit`) and `[PROMPT]` CANNOT be combined. This fails:

```bash
# WRONG - these ALL fail with "cannot be used with [PROMPT]"
codex review --uncommitted "Focus on security"          # ❌
codex review --base main "Check for race conditions"    # ❌
codex review --commit abc "Look for regressions"        # ❌
```

**Use the wrapper script instead**, which handles this automatically:

```bash
.claude/skills/codex-review/codex-review.sh --uncommitted "Focus on security"  # ✅
```

---

## Wrapper Script (Recommended)

The wrapper script at `.claude/skills/codex-review/codex-review.sh` handles all cases correctly:

### Review Uncommitted Changes (Default Instructions)

```bash
.claude/skills/codex-review/codex-review.sh --uncommitted
```

Uses native `codex review --uncommitted` for fast default review.

### Review Uncommitted Changes (Custom Instructions)

```bash
.claude/skills/codex-review/codex-review.sh --uncommitted "Focus on: bugs, security issues, race conditions, and edge cases. Skip style feedback. Cite file:line for each finding."
```

Uses `codex exec -s read-only` agent mode — the agent runs git commands to see changes, then reviews with your instructions.

### Review Against Base Branch

```bash
.claude/skills/codex-review/codex-review.sh --base main
.claude/skills/codex-review/codex-review.sh --base main "Security audit: check for injection, auth bypasses, data exposure."
```

### Review Specific Commit

```bash
.claude/skills/codex-review/codex-review.sh --commit abc123
.claude/skills/codex-review/codex-review.sh --commit abc123 "Check for regressions and error handling gaps."
```

### With Custom Model and Title

```bash
.claude/skills/codex-review/codex-review.sh --base main -m o3 --title "Add MFA verification" "Security review: auth flow, session handling, rate limiting."
```

### Custom Output Path

```bash
.claude/skills/codex-review/codex-review.sh --base main -o /tmp/my-review.md "Review for bugs."
```

Default output: `/tmp/codex-review-TIMESTAMP.md`

---

## Direct CLI Usage (No Custom Instructions)

When you don't need custom instructions, call `codex review` directly:

```bash
# These all work — no PROMPT argument
codex review --uncommitted
codex review --base main
codex review --commit abc123
codex review --base main --title "Feature name"
```

---

## Exec Mode (Custom Analysis of Specific Files)

For targeted file analysis outside of git diffs:

```bash
codex exec -s read-only -o /tmp/codex-review.md "Analyze these files for bugs, security issues, and logic errors: src/lib/services/auth-service.ts src/app/api/auth/route.ts. Output as markdown with severity levels (critical/high/medium/low) and file:line references."
```

---

## Output Handling

### Read Wrapper Output

The wrapper saves output to `/tmp/codex-review-TIMESTAMP.md` by default. Read the file after execution:

```bash
# Wrapper prints the output path to stderr
.claude/skills/codex-review/codex-review.sh --base main "Review for bugs"
# Then read the saved file
```

### Evaluate Findings

1. **Read the full output** - Don't cherry-pick findings
2. **Categorize by severity**:
   - **Critical**: Security vulnerabilities, data loss, crashes
   - **High**: Logic errors, race conditions, error handling gaps
   - **Medium**: Edge cases, suboptimal patterns, maintainability concerns
   - **Low**: Style preferences, minor improvements
3. **Filter noise** - Codex may flag false positives or stylistic preferences
4. **Cite evidence** - Report findings with file:line references
5. **Test hypotheses** - Verify findings before acting

---

## Model Selection

Use `-m <model>` for deeper analysis:

```bash
.claude/skills/codex-review/codex-review.sh --base main -m o3 "Deep security review"
```

Default model is fine for routine review.

---

## Examples

### Example 1: Quick Pre-Commit Review

```bash
.claude/skills/codex-review/codex-review.sh --uncommitted
```

### Example 2: Custom Security Review Before PR

```bash
.claude/skills/codex-review/codex-review.sh --base main "Security review focusing on: authentication flow, session handling, rate limiting, input validation, error messages leaking info. Cite file:line for every finding."
```

### Example 3: Debug Race Condition

```bash
codex exec -s read-only -o /tmp/codex-race.md "I'm debugging a race condition where user profile updates sometimes fail to save. Relevant files: src/lib/services/profile.service.ts src/app/api/profile/route.ts. Analyze for: concurrent access patterns, transaction handling, optimistic locking gaps, and state management issues."
```

### Example 4: Review with Different Model

```bash
.claude/skills/codex-review/codex-review.sh --base main -m o3 --title "Add cost caps" "Review Redis Lua scripts for atomicity, race conditions, and error handling. Check that all cost tracking is correct."
```

---

## Important Notes

### When Codex Disagrees with Architect

1. **Evaluate both perspectives** - Different models, different strengths
2. **Check evidence** - Which finding has clearer evidence?
3. **Test hypotheses** - Write tests to validate concerns
4. **Escalate if unclear** - Ask orchestrator to mediate
5. **Document decision** - Record why one perspective was chosen

### Limitations

- **No execution** - Codex analyzes static code, doesn't run it
- **Context window** - Large diffs may be truncated
- **False positives** - May flag non-issues
- **No project context** - Doesn't know Fundizzle architecture (5 collections, etc.)
- **Style noise** - May suggest style changes despite prompt to skip

---

## Troubleshooting

### Codex Not Installed

```bash
brew install codex
codex --version
```

### "Cannot be used with [PROMPT]" Error

You tried to combine a scope flag with a prompt. Use the wrapper script instead:

```bash
# Instead of: codex review --uncommitted "my prompt"
.claude/skills/codex-review/codex-review.sh --uncommitted "my prompt"
```

### Output Too Large or Timeout

Break into smaller chunks by reviewing specific directories:

```bash
codex exec -s read-only -o /tmp/codex-auth.md "Review src/lib/services/auth*.ts for security vulnerabilities."
codex exec -s read-only -o /tmp/codex-api.md "Review src/app/api/auth/ for input validation and error handling."
```

---

**Skill Status**: ACTIVE
