# 🗂️ project-indexer — Claude Code Skill

A Claude Code skill that auto-indexes any project at session start, so Claude
goes **directly to the right file** instead of wasting tokens exploring build
output and dependency folders.

**Works with:** Laravel · Next.js · Laravel + Next.js fullstack · Vue · Nuxt · Node.js · Python · Generic

---

## The Problem

When you ask Claude Code to find a controller, model, or component in a
fullstack project, it often wastes tokens scanning generated artifacts:

```
.next/dev/server/app/[locale]/(generated)/tenant/appointments/page.js
.next/dev/static/chunks/app/[locale]/(generated)/tenant/...
vendor/laravel/framework/src/...
node_modules/react/...
```

This skill fixes that by giving Claude a **pre-built map** of your source files
with purpose labels — so it reads one file instead of scanning hundreds.

---

## Installation

### Method 1 — Plugin (recommended)

```bash
# 1. Add the marketplace (GitHub repo)
/plugin marketplace add ahmadhozien/claude-project-indexer

# 2. Install the plugin (suffix is the marketplace name)
/plugin install project-indexer@claude-project-indexer
```

### Method 2 — Manual

```bash
# Clone into your global Claude skills folder
git clone https://github.com/ahmadhozien/claude-project-indexer.git ~/.claude/skills/claude-project-indexer

# Or for a single project only
git clone https://github.com/ahmadhozien/claude-project-indexer.git .claude/skills/claude-project-indexer
```

> **Windows path:** `C:\Users\<YourName>\.claude\skills\claude-project-indexer`

---

## Usage

Once installed, a `SessionStart` hook (`hooks/hooks.json`) runs the indexer
**automatically at the start of every session** — no need to ask. It:

1. Runs `index-project.py` against your project root (`${CLAUDE_PROJECT_DIR}`)
2. Writes/refreshes `PROJECT_INDEX.md`
3. Injects a session-start reminder into your `CLAUDE.md` so Claude reads the
   index before any file lookup

> **Requires `python` (or the `py` launcher) on your system PATH.** The hook is
> silent on success; if Python isn't found, nothing happens and no index is
> generated. Verify with `python --version` in a normal terminal.

You can also trigger it manually:

```
"index this project"
"map the codebase"
"what files do we have"
```

Or run the script directly from your project root:

```bash
python ~/.claude/skills/claude-project-indexer/project-indexer/scripts/index-project.py

# Verbose output
python ...index-project.py --verbose

# Point at a specific project
python ...index-project.py --root /path/to/project
```

---

## What Gets Generated

A `PROJECT_INDEX.md` in your project root. Example output for a Laravel + Next.js project:

```markdown
# PROJECT_INDEX.md
> Auto-generated on 2026-06-15 10:30. Regenerate: python scripts/index-project.py

## Stack
Laravel (PHP) + Next.js (React/TypeScript)
- Backend root: `backend/`
- Frontend root: `frontend/`

## ⚠️ Never Explore These Dirs
`.next/` `node_modules/` `vendor/` `dist/` `build/` `.git/`

## Route Summary (Laravel)
**api.php**
  `GET` `/api/public/clinics/{domain}`
  `POST` `/api/public/appointments`
  `GET` `/api/tenant/patients`
  ...

## Controllers
- `backend/app/Http/Controllers/Api/Tenant/PublicController.php` — public-facing API controller
- `backend/app/Http/Controllers/Api/Tenant/PatientController.php` — API controller

## Models
- `backend/app/Models/Patient.php` — model
- `backend/app/Models/Tenant/Patient.php` — tenant-scoped model

## Components
- `frontend/src/components/booking/BookingModal.tsx` — modal/dialog component
- `frontend/src/components/booking/steps/PatientDetailsStep.tsx` — multi-step form step

## i18n
- `frontend/messages/ar.json` — translations (ar)
- `frontend/messages/en.json` — translations (en)
```

---

## Supported Stacks

| Stack | Detected by | Sections generated |
|---|---|---|
| Laravel | `artisan` + `app/Http/` | Routes, Controllers, Models, Services, Requests, Migrations |
| Next.js | `next.config.*` | Pages, Components, Hooks, Stores, Lib/Utils, i18n, Types |
| Vue / Nuxt | `nuxt.config.*` | Same as Next.js |
| Python | `requirements.txt` / `manage.py` | Python Source |
| Generic | fallback | Source Files |

Fullstack monorepos (e.g. `backend/` + `frontend/` subdirs) are auto-detected.

---

## .gitignore

The generated index is a build artifact — add it to `.gitignore`:

```
PROJECT_INDEX.md
```

Or commit it if you want teammates to benefit without running the script.

---

## Requirements

- Python 3.7+ (no external dependencies — stdlib only)
- Claude Code with skills support

---

## License

MIT
