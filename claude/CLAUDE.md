# General

- Think in English, but generate responses in Japanese
- Implement based on Agile-like SDD and Kent Beck's TDD using Claude Code's slash commands, hooks, and agents
  - TDD: [@~/.claude/rules/coding_guideline.md](./rules/coding_guideline.md)
  - SDD: [@~/.claude/rules/asdd_guideline.md](./rules/asdd_guideline.md)
- When suspecting issues with given components, investigate evidence and present it to the user
- Prefer jj (Jujutsu) over Git for all VCS operations
- Don't perform the following tasks without user instructions:
  - Start the next task
  - Git commit and push
- Directory names: Use hyphens (-) as separators (ex: claude-scripts)
- File names: Use underscores (_) as separators (ex: lint_format.sh)
- When writing commit messages, follow Conventional Commits rules, and write it in English
- Use "，", and "．" in writing in Japanese, instead of "。" and "、"

## Project Context

- Product overview, features, and use cases: @./.kiro/steering/product.md
- Architecture, technology stack, and development environment: @./.kiro/steering/tech.md
- Directory structure, coding conventions, and naming rules: @./.kiro/steering/structure.md
- Spec (intent, requirements, approach, status) by feature: @./.kiro/specs/{feature}/spec.md

## Task Management

- Defer to user judgment when workflow fails midway

## Coding Guideline

- [@~/.claude/rules/coding_guideline.md](./rules/coding_guideline.md)
- [@~/.claude/rules/jj_guideline.md](./rules/jj_guideline.md)

### Coding Style

- Refer to language and library-specific rules in @~/.claude/rules/**
- Create only the classes and functions in @./.kiro/specs/{feature}/spec.md or @./docs/class.pu
- Write code comments in English

## Review

When receiving PR review requests from users, review code from the following perspectives:

- Verify all specifications are met
- Check all checklist items are completed when tasks have checklists
- Check for typos
- Verify codebase consistency is maintained
- Suggest better implementations to users when available
