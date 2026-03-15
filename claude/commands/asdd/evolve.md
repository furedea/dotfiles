---
description: Evolve spec.md when requirements change during implementation
allowed-tools: Read, Edit, Glob
argument-hint: <feature-name>
---

# Spec Evolution

<background_information>
- **Mission**: Update spec.md when requirements change, maintaining consistency across all sections
- **Success Criteria**:
  - Changes proposed in diff format before applying
  - Human approval required before any spec.md modification
  - Requirements, Approach, and Status sections stay in sync
  - Updated timestamp in frontmatter
</background_information>

<instructions>

## Core Task

Read the current spec and propose changes based on conversation context. Apply changes only after human approval.

## Triggers

This command handles two scenarios:
- Human-initiated: User wants to add, modify, or remove requirements
- AI-initiated: Implementation agent reported a blocker and human approved a change

## Execution Steps

### Step 1: Resolve Feature Name and Load Spec

`$ARGUMENTS` may be a prefix. Resolve to full feature name:

1. Glob `.kiro/specs/$ARGUMENTS*/` for matching directories
2. If exactly 1 match: use that feature name
3. If multiple matches: list them and ask user to be more specific
4. If 0 matches: report error, suggest `/asdd:init`

Read `.kiro/specs/{resolved-name}/spec.md`

### Step 2: Identify Changes

From conversation context, determine:
- Requirements to add (new REQ-IDs, continue sequential numbering)
- Requirements to modify (changed acceptance criteria)
- Requirements to remove (no longer needed)
- Approach changes driven by requirement changes

### Step 3: Present Proposal

Show changes in diff format:

```
spec.md changes:

Requirements:
+ REQ-005: [new requirement in EARS format]
~ REQ-002: [old] → [new] (reason: [evidence])
- REQ-003: removed (reason: [evidence])

Approach:
+ Added: [new architectural decision]
~ Changed: [old] → [new]

Status:
+ - [ ] REQ-005: [brief title]
- - [ ] REQ-003: [removed]
```

Wait for human approval before proceeding.

### Step 4: Apply Changes

After approval only:
- Update Requirements section
- Update Approach section if needed
- Update Status section (add/remove checkboxes)
- Update frontmatter `updated` timestamp
- Keep `status` field unchanged (do not revert to `draft`)

</instructions>

## Output Description

Provide output in the same language as the spec:

1. **Current State**: Brief summary of existing spec
2. **Proposed Changes**: Diff format as shown above
3. **Impact**: Which existing requirements are affected
4. **Next Steps**: After approval, continue with `/asdd:impl {feature-name}`

**Format**: Concise, Markdown headings

## Safety & Fallback

- **Spec Not Found**: Report error with path, suggest `/asdd:init`
- **No Changes Identified**: Ask user to describe what they want to change
- **Conflicting Changes**: Highlight conflicts and ask user to resolve
- **Never apply changes without explicit approval**
