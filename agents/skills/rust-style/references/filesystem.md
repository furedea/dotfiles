# Filesystem Operations

- Use `Path` and `PathBuf` for paths. Do not build paths with string concatenation.
- Treat source tree traversal and symlink creation as separate behaviors.
- Do not follow symlinks while traversing source trees unless the behavior is explicitly required and tested.
- Use `DirEntry::file_type()` instead of `Path::is_dir()` when symlink behavior matters.
- Keep file-writing operations behind small functions that are easy to test with temporary directories.
- Distinguish files fully owned by the project from files also modified by users or external tools.
- Prefer writing to a temporary file and replacing the target when partial writes would be harmful.

Symlink-aware traversal without following symlinks:

```rust
use anyhow::{Context, Result};
use std::path::{Path, PathBuf};

pub fn collect_regular_files(dir: &Path) -> Result<Vec<PathBuf>> {
    let mut files = Vec::new();
    collect_regular_files_into(dir, &mut files)?;
    files.sort();
    Ok(files)
}

fn collect_regular_files_into(dir: &Path, files: &mut Vec<PathBuf>) -> Result<()> {
    for entry in std::fs::read_dir(dir)
        .with_context(|| format!("failed to read directory {}", dir.display()))?
    {
        let entry = entry?;
        let file_type = entry.file_type()?;
        let path = entry.path();

        if file_type.is_symlink() {
            continue;
        }
        if file_type.is_dir() {
            collect_regular_files_into(&path, files)?;
        } else if file_type.is_file() {
            files.push(path);
        }
    }
    Ok(())
}
```
