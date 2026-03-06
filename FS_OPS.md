# Snappy PuTTy Filesystem Ops Contract

## Inline Parsing

Two-path filesystem actions support both inline forms:

- `copy <src> to <dst>`
- `copy <src> <dst>`
- `move <src> to <dst>`
- `move <src> <dst>`
- `rename <src> to <dst>`
- `rename <src> <dst>`

Optional filler words (`file`, `please`, `called`) are ignored only when they are standalone tokens.

`destination path>` follow-up prompts are shown only when a two-path action has a source but no destination (for example `copy README.md`).

## Destination Semantics

For `copy`, `move`, and `rename`, destination is interpreted as:

- Directory destination:
  - if destination already exists and is a directory
  - or destination ends with `/` or `\`
  - behavior: append source filename
- File destination:
  - otherwise, destination is used as the target file path

Examples:

- `copy README.md sandbox/` -> target `sandbox/README.md`
- `copy README.md sandbox/README.md` -> target `sandbox/README.md`

## Planning and Apply

- Workspace-root enforcement applies to all resolved paths.
- If destination parent directory is missing, planning inserts a `mkdir` op before copy/move/rename.
- Existing destinations require explicit overwrite confirmation in the REPL (`OVERWRITE`).
- Apply uses Python-native operations:
  - copy: `shutil.copy2(src, dst)`
  - move: `shutil.move(src, dst)`
  - rename: `Path.rename(dst)`
