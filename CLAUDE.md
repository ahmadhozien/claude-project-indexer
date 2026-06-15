# Claude Project Indexer — Plugin Marketplace

## Available Skills

| Plugin name | Install command | What it does |
|---|---|---|
| `project-indexer` | `/plugin install project-indexer@claude-project-indexer` | Auto-indexes any project at session start; prevents blind file-system scanning |

> First add the marketplace: `/plugin marketplace add ahmadhozien/claude-project-indexer`. The install suffix `@claude-project-indexer` is the marketplace name (from `.claude-plugin/marketplace.json`), not the GitHub repo.

## Description

A single-skill repository. The `project-indexer` skill:

- Detects your stack (Laravel, Next.js, fullstack, Vue, Nuxt, Python, generic)
- Runs `scripts/index-project.py` to generate `PROJECT_INDEX.md`
- Instructs Claude to read the index before any file lookup
- Saves tokens by skipping generated dirs (`.next/`, `vendor/`, `node_modules/`)

## Requirements

Python 3.7+ · No external dependencies
