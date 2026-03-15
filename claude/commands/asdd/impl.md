---
description: Execute TDD implementation for agile-like spec requirements
allowed-tools: Read, Edit, Task
argument-hint: <feature-name> [req-ids] [-y]
---

# Implementation Executor

## Parse Arguments

- Feature name: `$1`
- Requirement IDs: `$2` (optional)
  - Format: "REQ-001" (single) or "REQ-001,REQ-002" (multiple)
  - If not provided: Execute all pending requirements

## Resolve Feature Name

`$1` may be a prefix. Resolve to full feature name:

1. Glob `.kiro/specs/$1*/` for matching directories
2. If exactly 1 match: use that feature name
3. If multiple matches: list them and ask user to be more specific
4. If 0 matches: report error, suggest `/asdd:init`

Use the resolved name as `$1` for all subsequent steps.

## Validate

Check that spec exists and is ready:

- Read `.kiro/specs/$1/spec.md` frontmatter `status` field

### Approval Gate

If `-y` flag is present in arguments: skip approval gate, auto-approve.

If `status: draft` (and no `-y` flag):
- Warn: "This spec has not been reviewed yet. The status is still `draft`."
- Ask: "Have you reviewed the spec and want to proceed? [y/N]"
- If approved: Update frontmatter to `status: approved`, then continue
- If declined: Stop and suggest reviewing `.kiro/specs/$1/spec.md`

If `status: approved` or `status: in-progress`: Proceed directly.

If `status: completed`: Inform user all requirements are already done.

## Invoke Subagent

Delegate TDD implementation to asdd-impl-agent:

```
Task(
  subagent_type="asdd-impl-agent",
  description="Execute TDD implementation",
  prompt="""
Feature: $1
Spec directory: .kiro/specs/$1/
Target requirements: {parsed req IDs or "all pending"}

File patterns to read:
- .kiro/specs/$1/spec.md
- .kiro/steering/*.md
"""
)
```

## Display Result

Show subagent summary to user, then provide next step guidance:

### Commands

Execute specific requirement(s):
- `/asdd:impl feature-name REQ-001` - Single requirement
- `/asdd:impl feature-name REQ-001,REQ-002` - Multiple requirements

Execute all pending:
- `/asdd:impl feature-name` - All unchecked requirements

Check progress:
- `/asdd:status feature-name`

Evolve spec if needed:
- `/asdd:evolve feature-name`
