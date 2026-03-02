Enhance Snappy PuTTy with rotating personality-based loading status messages using Rich.

Goals

Add a reusable “heartbeat” spinner shown whenever Snappy PuTTy is processing user input (agent calls or safe tool execution).

Messages should rotate randomly from a predefined list to keep it lively but not noisy.

Spinner must disappear cleanly before rendering final output (use transient=True).

Must work in both REPL mode and CLI subcommands.

Must not break pytest.

Implementation Requirements

Create a new module (e.g. status.py) that defines:

A list STATUS_LINES containing short playful messages aligned with Snappy PuTTy’s personality, for example:

"🐶 Sniffing around..."

"🐾 Fetching a plan..."

"🧠 Chewing on that command..."

"🔎 Inspecting the filesystem..."

"📦 Packing things carefully..."

"☁️ Consulting the cloud spirits..."

"🛠️ Assembling a safe plan..."

A function get_status_message(mode: str | None = None) -> str that:

Randomly selects a message

Optionally adjusts message based on mode ("ask", "explain", "fs", "cloud")

Implement a reusable helper in render.py (or status module):
def busy(message: str | None = None):
returns a Rich Status context manager using SpinnerColumn + TextColumn
Use transient=True so spinner disappears after completion

Integrate spinner usage into:
- handle_ask
- handle_explain
- Any safe filesystem operations
Example pattern:
with busy(get_status_message("ask")):
result = run_agent_or_tools(...)

Add environment flag to disable spinner in tests:
If environment variable SNAPPY_PUTTY_NO_SPINNER == "1",
skip spinner and execute normally.

Update REPL loop so spinner appears before processing input and disappears before rendering output.

Add/adjust tests:
- Ensure CLI still exits cleanly
- Ensure setting SNAPPY_PUTTY_NO_SPINNER=1 suppresses spinner
- Ensure pytest passes

Constraints

Keep messages concise (one short line each)

Do not overuse emojis (max one per line)

Do not print spinner artifacts in final output

Maintain cross-platform compatibility

After implementation, ensure:

pytest -q passes

snappy_putty REPL shows rotating status messages

Spinner disappears before final output renders
