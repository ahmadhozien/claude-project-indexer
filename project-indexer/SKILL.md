---
name: project-indexer
description: "Auto-index any project before starting work. Trigger at the start of every Claude Code session, or when the user says 'index this project', 'map the codebase', 'what files do we have', or before any feature work that requires exploring the codebase. Reads PROJECT_INDEX.md if it exists and is fresh; regenerates it if missing or stale. Prevents wasting tokens on blind file-system exploration. Supports Laravel, Next.js, Laravel+Next.js fullstack, Vue, Nuxt, Node, Python, and generic projects."
---

# Project Indexer

## Purpose
Build and maintain a `PROJECT_INDEX.md` that gives Claude an instant map of
any project — so it never has to explore blindly or read build artifacts like
`.next/`, `vendor/`, or `node_modules/`.

**Token savings:** Instead of searching 20+ generated files to find one
controller, Claude reads one index and goes directly to the right file.

---

## Rules Claude Must Follow

1. **At session start**: check if `PROJECT_INDEX.md` exists in the project root.
2. **If missing or stale**: run `python scripts/index-project.py` (skill-local) or
   `python index-project.py` if the script is in PATH.
3. **Never explore** `.next/`, `vendor/`, `node_modules/`, `dist/`, `build/`,
   `.git/`, `storage/bootstrap/cache/` — they are generated/dependency folders.
4. **Always read `PROJECT_INDEX.md` first** before searching for any file,
   controller, component, model, route, or hook.
5. **After creating a new file**: append it to the relevant section in
   `PROJECT_INDEX.md` without full regeneration.

---

## First-Run: Inject Hook into CLAUDE.md

The **very first time** this skill runs on a project (i.e. no `PROJECT_INDEX.md`
exists yet), Claude must also inject a persistent hook into the project's
`CLAUDE.md` so the index is checked automatically on every future session —
without the user needing to remember to ask.

**Step 1:** Run the indexer:
```bash
python scripts/index-project.py
```

**Step 2:** Inject the hook into `CLAUDE.md`. The script handles this
automatically via the `--inject-claude-md` flag (already called internally).
But if running manually, Claude should check whether `CLAUDE.md` already
contains the marker `<!-- project-indexer -->`. If not, append the block below:

```markdown
<!-- project-indexer -->
## Session Start — Project Index
Before any task, always check `PROJECT_INDEX.md` in the project root.
- If it does not exist or source files are newer than it → run: `python scripts/index-project.py`
- Never explore `.next/`, `vendor/`, `node_modules/`, `dist/`, `build/`, `.git/`
- Use the index to locate files directly instead of scanning the filesystem
<!-- /project-indexer -->
```

**This injection is idempotent** — the script checks for the marker and never
duplicates the block.

---

## Session Start Workflow

```
1. Does PROJECT_INDEX.md exist?
   ├── No  → run: python scripts/index-project.py  (also injects CLAUDE.md hook)
   └── Yes → is it stale?
              ├── Stale → run: python scripts/index-project.py
              └── Fresh → read PROJECT_INDEX.md and proceed
```

**Check staleness (bash):**
```bash
INDEX_TIME=$(python -c "import os; print(int(os.path.getmtime('PROJECT_INDEX.md')))" 2>/dev/null || echo 0)
NEWEST=$(find . \( -name "*.php" -o -name "*.tsx" -o -name "*.ts" -o -name "*.js" \) \
  | grep -v node_modules | grep -v .next | grep -v vendor | grep -v dist \
  | xargs stat -c %Y 2>/dev/null | sort -n | tail -1)
[ "${NEWEST:-0}" -gt "$INDEX_TIME" ] && echo "stale" || echo "fresh"
```

---

## Reading the Index

| Section | When to use |
|---|---|
| `## Stack` | Understand project type before any task |
| `## Entry Points` | Find app root, main config, env files |
| `## Route Summary` | Find API endpoints by URL pattern (Laravel) |
| `## Controllers` | Find backend logic by feature name |
| `## Models` | Find data models by entity name |
| `## Pages & Layouts` | Find Next.js pages by route |
| `## Components` | Find frontend UI by feature or screen name |
| `## Hooks / Stores` | Find shared React logic |
| `## Lib / Utils / API Clients` | Find fetchers, formatters, auth utils |
| `## i18n` | Find translation files and key namespaces |
| `## Types` | Find TypeScript type definitions |

---

## After Creating New Files

Append immediately — do not re-run the full script for a single new file:

```markdown
## Components
...
- `frontend/src/components/booking/PatientLookup.tsx` — patient lookup by phone/national ID
```
