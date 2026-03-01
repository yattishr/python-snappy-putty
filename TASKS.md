# Snappy PuTTy – Task Board

## Phase 0 – Bootstrap
- [ ] Scaffold repo + pyproject + src layout
- [ ] Add deps: openai-agents, typer, rich, python-dotenv
- [ ] Add SKILLS.md + TASKS.md + README + .env.example
- [ ] Add smoke test

## Phase 1 – CLI Skeleton (Typer + Rich)
- [x] `ask`, `explain`, `doctor` commands
- [x] Rich rendering: panels + table

## Phase 2 – Context
- [x] OS, cwd
- [x] tool detection (which)
- [x] git status
- [x] project type detection

## Phase 3 – Agent Core (OpenAI Agents SDK)
- [x] agent instructions aligned to SKILLS.md
- [x] Pydantic schema parsing
- [x] runner wiring

## Phase 4 – Safety
- [x] regex-based risk scoring
- [x] warnings + safer alternatives

## Phase 5 – Skills
- [ ] file listing skill
- [ ] gcloud deploy planning skill (Cloud Run default)
