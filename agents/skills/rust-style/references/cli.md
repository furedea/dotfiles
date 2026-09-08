# CLI Code

- Use typed structs and enums for CLI input.
- Keep argument parsing separate from execution.
- Do not perform filesystem or network work while parsing CLI arguments.
- Human-readable command results go to stdout.
- Progress, warnings, and diagnostics go to stderr.
- Machine-readable output must not be mixed with human logs.
- Keep exit codes coarse but meaningful enough for CI.

```rust
#[derive(Debug, clap::Parser)]
pub struct Cli {
    #[command(subcommand)]
    pub command: Command,
}

#[derive(Debug, clap::Subcommand)]
pub enum Command {
    Render(RenderArgs),
    Verify(VerifyArgs),
}
```
