Clarification prompt accepts command-shaped input as raw answer, causing malformed plan generation

When Snappy is waiting for a destination path during clarification, and you type a full new command like:
```
copy README.md README_manual_12.md
```

it treats that entire string as the clarification answer, then builds a nonsense plan:

- goal becomes copy README.md to copy README.md README_manual_12.md
- destination becomes just copy
- it proceeds into confirmation instead of rejecting the input or preserving clarification state

That is not catastrophic, but it is definitely a clarification-input interpretation bug.

## What it means

Snappy is currently assuming:

“While clarification is pending, all input is answer-shaped.”

That assumption breaks when the user actually gives command-shaped input.

So the system is protected from nested goal corruption, but it is still too eager to reinterpret command-like text as clarification data.


## Why it matters

Because this is exactly the sort of thing that will get nastier in M4:

once workflow continuation is persisted
once pending state becomes durable
once command-vs-answer routing matters even more

Right now it is a contained UX/control bug. Later it could become workflow pollution.

Recommended fix direction

When a clarification prompt is active, Snappy should distinguish between:

Allowed answer-shaped input

Examples:

README_manual_12.md
tests/
./output.txt
Suspicious command-shaped input

Examples:

copy README.md README_manual_12.md
move file1 file2
status

For suspicious command-shaped input, Snappy should do one of these:

reject it and say:
“You have a pending question. Answer it, or type cancel to abandon the current goal.”
optionally allow an explicit escape mechanism later, but not now

The first option is enough.
