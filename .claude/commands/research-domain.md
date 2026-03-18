---
description: Build or update a domain expert knowledge base
user_invocable: true
---

# Research Domain

Build a comprehensive, implementation-focused domain expert knowledge base.

## Step 1: Scope the domain

Ask the user:
- Which domain to research (or create new)
- Specific aspects most relevant to our wildfire detection system
- Any known resources, papers, or implementations to include

## Step 2: Deep research

Use `/perplexity-web` and `/chatgpt-web` for broad synthesis queries:
- Current state-of-the-art implementations (not just papers)
- Open source libraries and frameworks
- API documentation and access patterns
- Known pitfalls and production gotchas
- Algorithm pseudocode and reference implementations

Use `WebSearch` and `WebFetch` for specific technical documentation:
- Official API docs
- Library documentation (use context7 MCP)
- GitHub repositories with reference implementations
- Stack Overflow / GIS Stack Exchange for practical solutions

## Step 3: Build domain files

Write the 5 standard files in `context/domain_briefs/{domain-slug}/`, plus any custom files the domain requires:

### Standard files (always create these):

#### DOMAIN.md (~800-1200 words)
- Overview of the domain and why it matters for our system
- Key concepts a practitioner must understand
- Current state of practice (not just research)
- Specific relevance to XPRIZE wildfire detection in NSW Australia

#### algorithms.md (~1000-2000 words)
- Core algorithms with pseudocode or step-by-step descriptions
- Key parameters and their typical values
- Reference implementations (links to code/repos)
- Performance characteristics (speed, accuracy, compute requirements)

#### apis_and_data_access.md (~800-1500 words)
- Specific API endpoints, authentication methods, rate limits
- Data formats and how to parse them
- Registration/key requirements
- Example requests and responses
- Latency characteristics of each access path

#### code_patterns.md (~800-1500 words)
- Recommended libraries and frameworks (with versions)
- Common implementation patterns
- Code snippets for key operations
- Architecture patterns that work well for this domain

#### pitfalls.md (~500-1000 words)
- What breaks in practice (not in theory)
- Edge cases specific to our use case (Australia, bushfire, Himawari)
- Common mistakes and how to avoid them
- Performance traps and how to work around them

### Custom files (add as needed):
If the domain has content that doesn't fit cleanly into the 5 standard files, create additional files. Examples:
- `sensor_specifications.md` — Detailed band tables, resolution specs, calibration constants
- `thresholds_reference.md` — Lookup tables of tunable parameters
- `training_data_catalog.md` — Where to get labeled datasets, their characteristics
- `reference_implementations.md` — Links to open-source code with notes on quality/applicability
- `{sensor_name}_details.md` — Sensor-specific deep dives (e.g., `himawari_ahi.md`)

Use judgment — if a topic needs its own file to be comprehensive, give it one.

## Step 4: Validate

Present completed files to user for review. Iterate until the expert is comprehensive enough to guide implementation.

## Step 5: Register

Ensure the domain is listed in `.claude/CLAUDE.md` under "Available domains".
