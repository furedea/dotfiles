---
description: Initialize a new agile-like spec with intent, requirements, approach, and rules
allowed-tools: Read, Write, Glob
argument-hint: <project-description>
---

# Agile-like SDD - Spec Initialization

<background_information>

- **Mission**: Generate a complete spec.md from a project description in a single step
- **Success Criteria**:
    - spec.md created with Intent, Requirements (EARS format), Approach, Rules, and Status
    - Requirements have numeric IDs (REQ-001, REQ-002, ...)
    - Status checkboxes correspond to each requirement ID
    - Frontmatter status is set to `draft` </background_information>

<instructions>

## Core Task

Generate a unique feature name from the project description ($ARGUMENTS) and create a complete spec.md.

## Execution Steps

### Step 1: Check Uniqueness

- Use Glob to check `.kiro/specs/` for existing directories
- Generate a kebab-case feature name from the description
- If name conflicts, append numeric suffix (e.g., `feature-name-2`)

### Step 2: Load Context

- Read ALL steering files: Glob(`.kiro/steering/*.md`), then read each file

### Step 3: Generate spec.md

Generate spec.md with the following structure:

```
---
status: draft
created: {ISO 8601 timestamp}
updated: {ISO 8601 timestamp}
---

# {Feature Name}

## Intent
{1-2 lines explaining WHY this feature is needed}

## Requirements
{EARS-format requirements following the rules below}

## Approach
{Bullet-point architecture decisions, HOW not detailed design}

## Rules
This spec follows these rules during implementation:

### Blocker (stop and report immediately)
- Spec contradictions discovered during implementation
- Technical impossibility that prevents requirement fulfillment
- Missing boundary conditions / edge cases that affect correctness
- Spec assumption doesn't match actual codebase

### Not Allowed
- Style / naming preferences
- "Nice to have" feature additions
- Scope expansion beyond current requirements
- Architectural changes not driven by blockers above

### TDD Iron Law
- NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST
- Write code before the test? Delete it. Start over.
- NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE

## Status
{One checkbox per requirement}
```

#### Requirements Format (EARS)

EARS (Easy Approach to Requirements Syntax) patterns:

| Pattern | Syntax | Use Case |
| --- | --- | --- |
| Event-Driven | When [event], the [system] shall [response] | Responses to specific events |
| State-Driven | While [precondition], the [system] shall [response] | Behavior dependent on state |
| Unwanted Behavior | If [trigger], the [system] shall [response] | Error/failure handling |
| Optional Feature | Where [feature is included], the [system] shall [response] | Conditional features |
| Ubiquitous | The [system] shall [response] | Always-active requirements |
| Combined | While [precondition], when [event], the [system] shall [response] | Multiple conditions |

Keep EARS keywords (`When`, `If`, `While`, `Where`, `The [system] shall`) in English. Localize variable parts to the language used in the project description.

```
### REQ-001: [Brief title]
- When [event], the [system] shall [response]

### REQ-002: [Brief title]
- If [trigger], the [system] shall [response]
```

Each requirement:

- Has a unique numeric ID (REQ-001, REQ-002, ...)
- Uses exactly one EARS pattern per acceptance criterion
- Describes WHAT, not HOW
- Is testable and verifiable

#### Approach Format

Bullet points describing architecture decisions. NOT detailed design:

```
- Use [technology/pattern] for [purpose]
- [Component] handles [responsibility]
- Data stored in [storage] as [format]
```

#### Status Format

One checkbox per requirement:

```
- [ ] REQ-001: [Brief title]
- [ ] REQ-002: [Brief title]
```

### Step 4: Write Files

- Create directory: `.kiro/specs/{feature-name}/`
- Write `spec.md` to the directory

</instructions>

## Tool Guidance

- Use **Glob** to check existing spec directories and find steering files
- Use **Read** to load steering files, EARS rules, and spec template
- Use **Write** to create spec.md

## Output Description

Provide output in the same language as the project description:

1. **Generated Feature Name**: kebab-case name with brief rationale
2. **Summary**: 1-sentence overview of the spec
3. **Requirements Count**: Number of requirements generated
4. **Next Steps**:
    - Review the generated spec: `.kiro/specs/{feature-name}/spec.md`
    - When ready: `/asdd:impl {feature-name}`

**Format**: Concise (under 200 words), Markdown headings

## Safety & Fallback

- **Ambiguous Feature Name**: Propose 2-3 options and ask user to select
- **Steering Missing**: Warn that no project context was loaded, proceed with generation
- **Steering Missing**: Warn that no project context was loaded, proceed with generation
- **Directory Conflict**: Append numeric suffix and notify user
