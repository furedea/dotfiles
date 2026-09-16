# Python Project Tooling

## Package Management

- Use only `uv` for package management, don't use `pip`
- Install dependencies using `uv sync`
- Run tools using `uv run {tool}`
- Baseline tooling dependencies belong in template-defined dependency groups, not ad hoc commands
- Add project-specific dependencies using `uv add {package}`
- Add project-specific tool dependencies using `uv add --group <group> {package}`
- Upgrade pinned packages using `uv lock --upgrade-package {package}`
- Prohibited: `uv pip install`, `uv add --dev`, `@latest`

## Directory Structure

- Store production code including entry points in `./src` directory
- Store test code in `./tests` directory
- For an application or internal project, prefer flat module placement like `src/main.py`
- Use `src/<package_name>/` only when the project is explicitly a distributable package or library with a real package namespace
- If a tool or template generates `src/<package_name>/` by default, do not keep it unless the project actually needs package semantics

## File Standards

- Keep code within 119 characters per line (URLs may exceed this limit)
- Always include type hints
- Use ty for static type checking

## Static Type Checking

- ty should already be provided by the project's `typecheck` dependency group
- Run type checks using `uv run ty check`
- Check specific paths using `uv run ty check src tests`
- Use `uv run ty server` only for editor or language-server integration
- Do not introduce another type checker unless the existing project is already standardized on it
