---
description: Show agile-like spec progress and status
allowed-tools: Read, Glob
argument-hint: <feature-name>
---

# Spec Status

## Core Task

Read spec.md and display progress summary.

## Execution Steps

### Step 1: Resolve Feature Name and Load Spec

- If no argument: Glob `.kiro/specs/*/spec.md` and list all specs with their status
- If `$ARGUMENTS` provided, resolve prefix to full feature name:
    1. Glob `.kiro/specs/$ARGUMENTS*/` for matching directories
    2. If exactly 1 match: use that feature name
    3. If multiple matches: list them and ask user to be more specific
    4. If 0 matches: report error, suggest `/asdd:init`

Read `.kiro/specs/{resolved-name}/spec.md`

### Step 2: Parse Status

From spec.md:

- Read frontmatter `status` field (draft / approved / in-progress / completed)
- Count total requirements from Status section
- Count completed (`- [x]`) and pending (`- [ ]`) requirements
- Calculate completion percentage

### Step 3: Display Summary

```
## {Feature Name}

Status: {frontmatter status}
Progress: {completed}/{total} requirements ({percentage}%)

### Completed
- [x] REQ-001: ...
- [x] REQ-002: ...

### Pending
- [ ] REQ-003: ...
- [ ] REQ-004: ...
```

## Next Step Guidance

Based on status:

- `draft`: Review spec, then `/asdd:impl {feature}`
- `approved`: `/asdd:impl {feature}`
- `in-progress`: `/asdd:impl {feature}` to continue, or `/asdd:evolve {feature}` to change spec
- `completed`: All requirements done

## Safety & Fallback

- **Spec Not Found**: Report error, suggest `/asdd:init`
- **No Status Section**: Report format error, suggest recreating spec
- **Multiple Specs**: When no argument given, list all with brief status
