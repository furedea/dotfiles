# ADR-0030: Bootstrap the agent harness on servers without Nix

- Status: Accepted
- Date: 2026-09-16

In the context of using the personal agent harness from
[ADR-0016](0016_own_personal_agent_source.md) on shared Linux servers that offer
neither Nix nor root, facing a deployment path that existed only as the Home
Manager module, we decided for a repository-owned bootstrap script that installs
pinned user-space release binaries and a uv-managed Python 3.14 under the home
directory, renders `agents/` with the same `agent-harness` CLI, and pins hook
shebangs to that interpreter, and against installing single-user Nix on shared
hosts, relaxing the hooks to each server's system Python, adopting a second
configuration manager for non-Nix hosts, or committing per-host settings to this
public repository, to keep one harness source and one renderer across every
machine, accepting a second runtime lifecycle that
[ADR-0024](0024_manage_language_runtimes_with_nix.md) rejects for Nix-managed
hosts: version-pinned but hash-unverified downloads, x86_64-only release
binaries, and host-specific locations kept outside the repository.

The rendered harness stays at `~/.claude` and `~/.codex` because the providers
read those paths; only binaries, the interpreter, caches, and hook state move
through `~/.config/dotfiles/install_server.env`. Claude Code settings that the
provider writes at runtime survive re-rendering the same way the Home Manager
module preserves them, and `~/.config/dotfiles/claude_settings_override.json`
carries server-only differences such as disabling the sandbox where bubblewrap is
unavailable. ADR-0024 and [ADR-0027](0027_let_nix_own_python_entry_points.md)
continue to govern Nix-managed hosts; this decision scopes the exception to hosts
where Nix is not an option.
