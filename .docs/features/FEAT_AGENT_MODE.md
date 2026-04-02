# Snappy — Agent Mode Control Surface (Session Only)

## Goal
Replace environment-variable-based agent mode control with an interactive REPL command:

Instead of:

export SNAPPY_AGENT_MODE=off  
export SNAPPY_AGENT_MODE=passive  
export SNAPPY_AGENT_MODE=active  

Users should be able to run:

agent mode  
agent mode off  
agent mode passive  
agent mode active  

This control is **session-only** and must not persist to disk.

---

# GLOBAL RULES

- This is UI/runtime state only
- Do not change routing behavior
- Do not change execution behavior
- Do not change planning behavior
- Do not persist to disk
- Do not modify .snappy files
- Environment variable support must remain intact
- Session override must take precedence over environment variable
- Default mode must remain: off

---

# Supported Commands

Exact REPL commands only:

agent mode  
agent mode off  
agent mode passive  
agent mode active  

No natural language variants.

---

# Behavior

## 1. Inspect mode

Command:

agent mode

Output:

Agent Mode

Current: passive  
Source: session  

If using environment variable:

Agent Mode

Current: passive  
Source: environment  

If default:

Agent Mode

Current: off  
Source: default  

---

## 2. Set mode directly

Commands:

agent mode off  
agent mode passive  
agent mode active  

Output:

Agent mode set to: passive (session)

Rules:

- session only
- override environment variable
- case insensitive
- trim whitespace
- validate values

Invalid input:

agent mode chaos

Output:

Invalid mode. Choose: off, passive, active

---

## 3. Menu-style selector

If user runs:

agent mode

AND no argument provided, show selector:

Agent Mode

Current: passive

Select mode:
1. off
2. passive
3. active

Enter choice >

User enters:

1 → off  
2 → passive  
3 → active  

Then output:

Agent mode set to: passive (session)

---

## 4. Mode resolution precedence

Mode must resolve in this order:

1. session override  
2. environment variable  
3. default = off  

Implementation example:

def get_agent_mode():
    if session.agent_mode is not None:
        return session.agent_mode, "session"

    if os.getenv("SNAPPY_AGENT_MODE"):
        return os.getenv("SNAPPY_AGENT_MODE"), "environment"

    return "off", "default"

---

## 5. Status integration

Extend status output to include:

Agent feature mode: passive  
Agent mode source: session  

This must reflect runtime session changes.

---

## 6. Validation rules

Accepted values:

off  
passive  
active  

Case insensitive:

PASSIVE  
Passive  
pAsSiVe  

Whitespace tolerant:

agent mode     passive  

Invalid values must show:

Invalid mode. Choose: off, passive, active

---

## 7. Session storage

Store mode in session state only:

session.agent_mode = "passive"

Do not persist to disk  
Do not write to memory/session.json  
Do not write to config files  

---

## 8. Help integration

Update REPL help to include:

agent mode               Inspect or change agent runtime mode

---

## 9. Tests

Add tests for:

1. agent mode shows default
2. agent mode respects env var
3. agent mode off sets session mode
4. agent mode passive sets session mode
5. agent mode active sets session mode
6. session override beats env var
7. invalid mode handled
8. menu selection works
9. status reflects runtime change
10. case insensitive input works

---

## Expected UX

snappy> agent mode

Agent Mode

Current: passive

Select mode:
1. off
2. passive
3. active

Enter choice > 2

Agent mode set to: passive (session)


snappy> status

Agent feature mode: passive  
Agent mode source: session


snappy> agent mode active

Agent mode set to: active (session)


snappy> agent mode

Agent Mode

Current: active  
Source: session