# General

- Think in English, but generate responses in Japanese
- Use "，" and "．" in writing in Japanese, instead of "。" and "、"
- Implement based on Test-Spec Driven Development (TSDD) and Kent Beck's TDD:
    - TSDD: [@~/.claude/skills/tsdd/SKILL.md](./skills/tsdd/SKILL.md)
    - Coding guideline: [@~/.claude/rules/coding_guideline.md](./rules/coding_guideline.md)
    - Requirements live in executable tests; durable prose carries only Why.
- Directory names: Use hyphens (-) as separators (ex: claude-scripts)
- File names: Use underscores (\_) as separators (ex: lint_format.sh)
- Write code comments in English
- Prefer jj (Jujutsu) over Git for all VCS operations
- When writing commit messages, follow Conventional Commits rules, and write it in English
- For new projects, use flake.nix + `.envrc (use flake)` + `direnv allow` + language init (in that order). See `skills/nix-dev-init`.
- Don't perform the following tasks without user instructions:
    - Push (jj)

## Project Context

- Product overview, features, and use cases: @./.kiro/steering/product.md
- Architecture, technology stack, and development environment: @./.kiro/steering/tech.md
- Directory structure, coding conventions, and naming rules: @./.kiro/steering/structure.md
