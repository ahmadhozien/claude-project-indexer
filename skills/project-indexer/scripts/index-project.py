#!/usr/bin/env python3
"""
index-project.py — Universal Project Indexer for Claude Code
------------------------------------------------------------
Detects your stack, maps source files with purpose labels,
and writes PROJECT_INDEX.md at the project root.

Supports: Laravel, Next.js, Laravel+Next.js fullstack, Vue, Nuxt,
          plain Node, plain Python, and generic fallback.

Usage:
    python index-project.py              # run from project root
    python index-project.py --root /path/to/project
    python index-project.py --verbose    # show what's being scanned
"""

import os
import re
import sys
import json
import argparse
from datetime import datetime
from pathlib import Path
from collections import defaultdict

# ─── Configuration ────────────────────────────────────────────────────────────

EXCLUDED_DIRS = {
    ".next", "node_modules", "vendor", "dist", "build", ".git",
    ".nuxt", "__pycache__", ".venv", "venv", "env", "storage",
    "bootstrap/cache", ".turbo", "out", "coverage", ".cache",
    "public/build", "public/hot",
}

EXCLUDED_EXTENSIONS = {
    ".lock", ".log", ".map", ".min.js", ".min.css",
    ".jpg", ".jpeg", ".png", ".gif", ".svg", ".ico",
    ".woff", ".woff2", ".ttf", ".eot",
}

MAX_FILES_PER_SECTION = 200  # guard against huge projects

# ─── Stack Detection ──────────────────────────────────────────────────────────

def detect_stack(root: Path) -> dict:
    stack = {
        "laravel": False,
        "nextjs": False,
        "vue": False,
        "nuxt": False,
        "node": False,
        "python": False,
        "frontend_root": None,
        "backend_root": None,
    }

    # Laravel
    if (root / "artisan").exists() and (root / "app" / "Http").exists():
        stack["laravel"] = True
        stack["backend_root"] = root

    # Check subdirectories for backend/frontend split
    for subdir in root.iterdir():
        if not subdir.is_dir():
            continue
        if (subdir / "artisan").exists():
            stack["laravel"] = True
            stack["backend_root"] = subdir
        if (subdir / "next.config.js").exists() or (subdir / "next.config.ts").exists() or (subdir / "next.config.mjs").exists():
            stack["nextjs"] = True
            stack["frontend_root"] = subdir
        if (subdir / "nuxt.config.ts").exists() or (subdir / "nuxt.config.js").exists():
            stack["nuxt"] = True
            stack["frontend_root"] = subdir

    # Next.js at root
    if (root / "next.config.js").exists() or (root / "next.config.ts").exists() or (root / "next.config.mjs").exists():
        stack["nextjs"] = True
        if not stack["frontend_root"]:
            stack["frontend_root"] = root

    # Nuxt at root
    if (root / "nuxt.config.ts").exists() or (root / "nuxt.config.js").exists():
        stack["nuxt"] = True
        if not stack["frontend_root"]:
            stack["frontend_root"] = root

    # Vue (without Nuxt)
    pkg = root / "package.json"
    if pkg.exists():
        try:
            data = json.loads(pkg.read_text(encoding="utf-8"))
            deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
            if "vue" in deps and not stack["nuxt"]:
                stack["vue"] = True
            if "next" in deps:
                stack["nextjs"] = True
                if not stack["frontend_root"]:
                    stack["frontend_root"] = root
            stack["node"] = True
        except Exception:
            pass

    # Python
    if (root / "requirements.txt").exists() or (root / "pyproject.toml").exists() or (root / "manage.py").exists():
        stack["python"] = True
        if not stack["backend_root"]:
            stack["backend_root"] = root

    return stack


def describe_stack(stack: dict) -> str:
    parts = []
    if stack["laravel"]:
        parts.append("Laravel (PHP)")
    if stack["nextjs"]:
        parts.append("Next.js (React/TypeScript)")
    if stack["nuxt"]:
        parts.append("Nuxt (Vue/TypeScript)")
    if stack["vue"] and not stack["nuxt"]:
        parts.append("Vue.js")
    if stack["python"] and not stack["laravel"]:
        parts.append("Python")
    if stack["node"] and not stack["nextjs"] and not stack["nuxt"] and not stack["vue"]:
        parts.append("Node.js")
    return " + ".join(parts) if parts else "Unknown / Generic"


# ─── File Collectors ──────────────────────────────────────────────────────────

def walk(root: Path, extensions: set = None, max_depth: int = 10):
    """Yield (path, rel_path) for all matching files, skipping excluded dirs."""
    def _walk(path: Path, depth: int):
        if depth > max_depth:
            return
        try:
            for entry in sorted(path.iterdir()):
                if entry.is_dir():
                    if entry.name not in EXCLUDED_DIRS and not entry.name.startswith("."):
                        yield from _walk(entry, depth + 1)
                elif entry.is_file():
                    if any(entry.name.endswith(ext) for ext in EXCLUDED_EXTENSIONS):
                        continue
                    if extensions is None or entry.suffix in extensions:
                        yield entry, entry.relative_to(root)
        except PermissionError:
            pass

    yield from _walk(root, 0)


def label_file(rel: Path, content_sample: str = "") -> str:
    """Return a short purpose label for a file based on its path and content."""
    parts = rel.parts
    name = rel.stem.lower()
    suffix = rel.suffix.lower()

    # Laravel patterns
    if "Controllers" in parts or "controllers" in parts:
        if "Api" in parts or "api" in parts:
            return "API controller"
        if "Public" in name:
            return "public-facing API controller"
        return "controller"
    if "Models" in parts or "models" in parts:
        if "Tenant" in parts:
            return "tenant-scoped model"
        return "model"
    if "Migrations" in parts or "migrations" in parts:
        return "migration"
    if "Requests" in parts or "requests" in parts:
        return "form request / validation"
    if "Policies" in parts or "policies" in parts:
        return "authorization policy"
    if "Services" in parts or "services" in parts:
        return "service class"
    if "Jobs" in parts or "jobs" in parts:
        return "queued job"
    if "Events" in parts or "events" in parts:
        return "event"
    if "Listeners" in parts or "listeners" in parts:
        return "event listener"
    if "routes" in parts:
        return "route definitions"
    if "Middleware" in parts or "middleware" in parts:
        return "middleware"
    if "database/seeders" in str(rel) or "Seeders" in parts:
        return "seeder"
    if "factories" in str(rel).lower():
        return "factory"

    # Next.js / React patterns
    if "app" in parts and ("page.tsx" in parts or "page.jsx" in parts or name == "page"):
        return "Next.js page"
    if "app" in parts and ("layout.tsx" in parts or name == "layout"):
        return "Next.js layout"
    if "app" in parts and ("loading.tsx" in parts or name == "loading"):
        return "Next.js loading state"
    if "app" in parts and name.startswith("error"):
        return "Next.js error boundary"
    if "api" in parts and ("route.ts" in parts or name == "route"):
        return "Next.js API route"
    if "components" in parts:
        if "ui" in parts:
            return "UI primitive component"
        if "modal" in name or "dialog" in name:
            return "modal/dialog component"
        if "form" in name:
            return "form component"
        if "step" in name:
            return "multi-step form step"
        if "table" in name or "list" in name:
            return "data table/list component"
        if "button" in name or "badge" in name or "icon" in name:
            return "UI atom component"
        if "layout" in name or "header" in name or "sidebar" in name or "nav" in name:
            return "layout component"
        return "component"
    if "hooks" in parts:
        return "React hook"
    if "store" in parts or "stores" in parts or "zustand" in content_sample.lower() or "create(" in content_sample:
        return "state store"
    if "context" in name:
        return "React context/provider"
    if "lib" in parts or "utils" in parts or "helpers" in parts:
        if "api" in name or "client" in name or "fetch" in name:
            return "API client / fetcher"
        if "auth" in name:
            return "auth utility"
        if "format" in name or "date" in name:
            return "formatter / date util"
        return "utility / helper"
    if "types" in parts or name.endswith(".types") or name == "types":
        return "TypeScript types"
    if "messages" in parts or "locales" in parts or "i18n" in parts:
        lang = rel.stem
        return f"i18n translations ({lang})"
    if "middleware" in name and suffix in (".ts", ".js"):
        return "Next.js middleware"

    # Config files
    if name in ("next.config", "nuxt.config", "vite.config", "tailwind.config",
                 "tsconfig", ".env", ".env.example"):
        return "config"

    # Test files
    if "test" in name or "spec" in name or "tests" in parts or "__tests__" in parts:
        return "test"

    return ""  # no label — still included, just unlabeled


def format_line(rel: Path, label: str) -> str:
    path_str = str(rel).replace("\\", "/")
    if label:
        return f"- `{path_str}` — {label}"
    return f"- `{path_str}`"


# ─── Section Builders ─────────────────────────────────────────────────────────

def build_laravel_sections(root: Path, backend_root: Path, rel_prefix: str = "") -> dict:
    sections = defaultdict(list)

    def rp(p: Path) -> Path:
        """Relative to project root (not backend_root)."""
        try:
            r = p.relative_to(root)
        except ValueError:
            r = p.relative_to(backend_root)
        return r

    # Routes
    route_files = ["routes/api.php", "routes/web.php", "routes/tenant.php",
                   "routes/channels.php", "routes/console.php"]
    for rf in route_files:
        p = backend_root / rf
        if p.exists():
            sections["Routes"].append(format_line(rp(p), "route definitions"))

    # Controllers
    ctrl_root = backend_root / "app" / "Http" / "Controllers"
    if ctrl_root.exists():
        for f, rel in walk(ctrl_root, {".php"}):
            label = label_file(f.relative_to(backend_root))
            sections["Controllers"].append(format_line(rp(f), label))

    # Models
    model_root = backend_root / "app" / "Models"
    if model_root.exists():
        for f, rel in walk(model_root, {".php"}):
            label = label_file(f.relative_to(backend_root))
            sections["Models"].append(format_line(rp(f), label))

    # Services
    svc_root = backend_root / "app" / "Services"
    if svc_root.exists():
        for f, rel in walk(svc_root, {".php"}):
            sections["Services"].append(format_line(rp(f), "service class"))

    # Requests
    req_root = backend_root / "app" / "Http" / "Requests"
    if req_root.exists():
        for f, rel in walk(req_root, {".php"}):
            sections["Form Requests (Validation)"].append(format_line(rp(f), "validation"))

    # Middleware
    mw_root = backend_root / "app" / "Http" / "Middleware"
    if mw_root.exists():
        for f, rel in walk(mw_root, {".php"}):
            sections["Middleware"].append(format_line(rp(f), "middleware"))

    # Migrations (last 20 only — ordered)
    mig_root = backend_root / "database" / "migrations"
    if mig_root.exists():
        migrations = sorted(mig_root.glob("*.php"), reverse=True)[:20]
        for f in migrations:
            sections["Migrations (recent 20)"].append(format_line(rp(f), ""))

    # Config
    cfg_root = backend_root / "config"
    if cfg_root.exists():
        for f in sorted(cfg_root.glob("*.php")):
            sections["Config"].append(format_line(rp(f), "config"))

    return sections


def build_nextjs_sections(root: Path, frontend_root: Path) -> dict:
    sections = defaultdict(list)

    def rp(p: Path) -> Path:
        try:
            return p.relative_to(root)
        except ValueError:
            return p.relative_to(frontend_root)

    src_root = frontend_root / "src" if (frontend_root / "src").exists() else frontend_root

    # Pages (app router)
    app_root = src_root / "app"
    if not app_root.exists():
        app_root = frontend_root / "app"
    if app_root.exists():
        for f, rel in walk(app_root, {".tsx", ".ts", ".jsx", ".js"}):
            label = label_file(f.relative_to(frontend_root) if frontend_root in f.parents else rel)
            sections["Pages & Layouts"].append(format_line(rp(f), label))

    # Components
    comp_root = src_root / "components"
    if not comp_root.exists():
        comp_root = frontend_root / "components"
    if comp_root.exists():
        for f, rel in walk(comp_root, {".tsx", ".ts", ".jsx", ".js"}):
            try:
                sample = f.read_text(encoding="utf-8", errors="ignore")[:500]
            except Exception:
                sample = ""
            label = label_file(f.relative_to(frontend_root) if frontend_root in f.parents else rel, sample)
            sections["Components"].append(format_line(rp(f), label))

    # Hooks
    hooks_root = src_root / "hooks"
    if hooks_root.exists():
        for f, rel in walk(hooks_root, {".tsx", ".ts"}):
            sections["Hooks"].append(format_line(rp(f), "React hook"))

    # Stores
    for store_dir in ["store", "stores", "state"]:
        store_root = src_root / store_dir
        if store_root.exists():
            for f, rel in walk(store_root, {".tsx", ".ts", ".js"}):
                sections["Stores"].append(format_line(rp(f), "state store"))

    # Lib / utils
    for util_dir in ["lib", "utils", "helpers", "api"]:
        util_root = src_root / util_dir
        if util_root.exists():
            for f, rel in walk(util_root, {".tsx", ".ts", ".js"}):
                label = label_file(f.relative_to(frontend_root) if frontend_root in f.parents else rel)
                sections["Lib / Utils / API Clients"].append(format_line(rp(f), label))

    # Types
    for types_dir in ["types", "interfaces"]:
        types_root = src_root / types_dir
        if types_root.exists():
            for f, rel in walk(types_root, {".ts"}):
                sections["Types"].append(format_line(rp(f), "TypeScript types"))

    # i18n
    for i18n_dir in ["messages", "locales", "i18n", "translations"]:
        for base in [src_root, frontend_root, root]:
            i18n_root = base / i18n_dir
            if i18n_root.exists():
                for f in sorted(i18n_root.rglob("*.json")):
                    lang = f.stem
                    sections["i18n"].append(format_line(rp(f), f"translations ({lang})"))
                for f in sorted(i18n_root.rglob("*.ts")):
                    sections["i18n"].append(format_line(rp(f), "i18n config"))
                break

    # Middleware
    for mw_name in ["middleware.ts", "middleware.js"]:
        mw = src_root / mw_name
        if not mw.exists():
            mw = frontend_root / mw_name
        if mw.exists():
            sections["Config / Middleware"].append(format_line(rp(mw), "Next.js middleware"))

    # Config files
    for cfg in ["next.config.ts", "next.config.js", "next.config.mjs",
                "tailwind.config.ts", "tailwind.config.js",
                "tsconfig.json", ".env.example", ".env.local.example"]:
        p = frontend_root / cfg
        if p.exists():
            sections["Config / Middleware"].append(format_line(rp(p), "config"))

    return sections


def build_generic_sections(root: Path) -> dict:
    """Fallback for any other stack."""
    sections = defaultdict(list)
    extensions = {".py", ".js", ".ts", ".jsx", ".tsx", ".php", ".go", ".rb",
                  ".java", ".cs", ".rs", ".dart"}
    for f, rel in walk(root, extensions):
        label = label_file(rel)
        sections["Source Files"].append(format_line(rel, label))
        if len(sections["Source Files"]) >= MAX_FILES_PER_SECTION:
            sections["Source Files"].append("  *(truncated — too many files)*")
            break
    return sections


# ─── Entry Point Finder ───────────────────────────────────────────────────────

def find_entry_points(root: Path, stack: dict) -> list:
    entries = []
    candidates = [
        ".env", ".env.example", "README.md", "composer.json", "package.json",
        "artisan", "server.js", "index.js", "main.py", "manage.py",
        "docker-compose.yml", "docker-compose.yaml", "Makefile",
    ]
    for name in candidates:
        p = root / name
        if p.exists():
            label = {
                ".env": "environment variables (active)",
                ".env.example": "environment variable template",
                "README.md": "project documentation",
                "composer.json": "PHP dependencies",
                "package.json": "JS dependencies / scripts",
                "artisan": "Laravel CLI entry point",
                "docker-compose.yml": "Docker services",
                "docker-compose.yaml": "Docker services",
                "Makefile": "build / task runner",
            }.get(name, "entry point")
            entries.append(format_line(Path(name), label))

    # Also check subdir package.json / composer.json
    for subdir in root.iterdir():
        if subdir.is_dir() and subdir.name not in EXCLUDED_DIRS:
            for cfg in ["package.json", "composer.json", ".env.example"]:
                p = subdir / cfg
                if p.exists():
                    entries.append(format_line(p.relative_to(root), f"{cfg} in {subdir.name}/"))
    return entries


# ─── Route Extractor (quick summary) ─────────────────────────────────────────

def extract_route_summary(backend_root: Path, max_routes: int = 60) -> list:
    """Pull Route:: lines from Laravel route files for a quick reference."""
    lines = []
    route_files = list((backend_root / "routes").glob("*.php")) if (backend_root / "routes").exists() else []
    for rf in route_files:
        try:
            content = rf.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        file_label = rf.name
        file_routes = []
        for match in re.finditer(
            r"Route::(get|post|put|patch|delete|any)\s*\(\s*['\"]([^'\"]+)['\"]",
            content
        ):
            method = match.group(1).upper()
            path = match.group(2)
            file_routes.append(f"  `{method}` `{path}`")
        if file_routes:
            lines.append(f"\n**{file_label}**")
            lines.extend(file_routes[:max_routes])
            if len(file_routes) > max_routes:
                lines.append(f"  *(+{len(file_routes) - max_routes} more)*")
    return lines


# ─── CLAUDE.md Injector ───────────────────────────────────────────────────────

CLAUDE_MD_MARKER_START = "<!-- project-indexer -->"
CLAUDE_MD_MARKER_END   = "<!-- /project-indexer -->"

CLAUDE_MD_BLOCK = """<!-- project-indexer -->
## Session Start — Project Index
Before any task, always check `PROJECT_INDEX.md` in the project root.
- If it does not exist or source files are newer than it → run: `python scripts/index-project.py`
- Never explore `.next/`, `vendor/`, `node_modules/`, `dist/`, `build/`, `.git/`
- Use the index to locate files directly instead of scanning the filesystem
<!-- /project-indexer -->"""


def inject_claude_md(root: Path) -> str:
    """
    Inject the session-start hook into CLAUDE.md at the project root.
    - Creates CLAUDE.md if it doesn't exist.
    - Appends the block if the marker is absent (idempotent).
    - Replaces the block if it already exists (safe update).
    Returns one of: 'created' | 'injected' | 'updated' | 'already_present'
    """
    claude_md_path = root / "CLAUDE.md"

    if not claude_md_path.exists():
        claude_md_path.write_text(CLAUDE_MD_BLOCK + "\n", encoding="utf-8")
        return "created"

    existing = claude_md_path.read_text(encoding="utf-8")

    if CLAUDE_MD_MARKER_START not in existing:
        # Append with a blank line separator
        separator = "\n\n" if existing.rstrip() else ""
        claude_md_path.write_text(
            existing.rstrip() + separator + "\n" + CLAUDE_MD_BLOCK + "\n",
            encoding="utf-8"
        )
        return "injected"

    # Marker exists — check if block is identical to avoid unnecessary writes
    start_idx = existing.find(CLAUDE_MD_MARKER_START)
    end_idx   = existing.find(CLAUDE_MD_MARKER_END)
    if end_idx == -1:
        # Malformed — replace from start marker to end of file
        updated = existing[:start_idx].rstrip() + "\n\n" + CLAUDE_MD_BLOCK + "\n"
        claude_md_path.write_text(updated, encoding="utf-8")
        return "updated"

    end_idx += len(CLAUDE_MD_MARKER_END)
    current_block = existing[start_idx:end_idx]
    if current_block.strip() == CLAUDE_MD_BLOCK.strip():
        return "already_present"

    # Replace existing block
    updated = existing[:start_idx] + CLAUDE_MD_BLOCK + existing[end_idx:]
    claude_md_path.write_text(updated, encoding="utf-8")
    return "updated"


# ─── Writer ───────────────────────────────────────────────────────────────────

def write_index(root: Path, stack: dict, sections: dict, entries: list,
                route_summary: list, verbose: bool = False):
    out = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    out.append(f"# PROJECT_INDEX.md")
    out.append(f"> Auto-generated by `index-project.py` on {now}. Do not edit manually.")
    out.append(f"> Regenerate with: `python scripts/index-project.py`")
    out.append("")

    out.append("## Stack")
    out.append(describe_stack(stack))
    out.append("")

    if stack["backend_root"] and stack["backend_root"] != root:
        out.append(f"- **Backend root:** `{stack['backend_root'].relative_to(root)}`")
    if stack["frontend_root"] and stack["frontend_root"] != root:
        out.append(f"- **Frontend root:** `{stack['frontend_root'].relative_to(root)}`")
    out.append("")

    out.append("## ⚠️ Never Explore These Dirs")
    out.append("`.next/` `node_modules/` `vendor/` `dist/` `build/` `.git/` `storage/bootstrap/cache/`")
    out.append("")

    if entries:
        out.append("## Entry Points & Config")
        out.extend(entries)
        out.append("")

    if route_summary:
        out.append("## Route Summary (Laravel)")
        out.extend(route_summary)
        out.append("")

    for section_name, items in sections.items():
        if not items:
            continue
        out.append(f"## {section_name}")
        # Truncate large sections
        if len(items) > MAX_FILES_PER_SECTION:
            out.extend(items[:MAX_FILES_PER_SECTION])
            out.append(f"*(+{len(items) - MAX_FILES_PER_SECTION} more — narrow your search)*")
        else:
            out.extend(items)
        out.append("")

    index_path = root / "PROJECT_INDEX.md"
    index_path.write_text("\n".join(out), encoding="utf-8")
    print(f"✅ PROJECT_INDEX.md written ({len(out)} lines, {index_path.stat().st_size // 1024}KB)")
    print(f"   Stack: {describe_stack(stack)}")
    for s, items in sections.items():
        if items and verbose:
            print(f"   {s}: {len(items)} entries")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Universal Project Indexer for Claude Code")
    parser.add_argument("--root", default=".", help="Project root directory")
    parser.add_argument("--verbose", action="store_true", help="Show section counts")
    parser.add_argument("--skip-claude-md", action="store_true",
                        help="Do not inject the session-start hook into CLAUDE.md")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not root.exists():
        print(f"❌ Root not found: {root}", file=sys.stderr)
        sys.exit(1)

    print(f"🔍 Indexing: {root}")
    stack = detect_stack(root)
    print(f"   Detected: {describe_stack(stack)}")

    sections = defaultdict(list)
    entries = find_entry_points(root, stack)
    route_summary = []

    # Laravel
    if stack["laravel"] and stack["backend_root"]:
        be = stack["backend_root"]
        laravel_sections = build_laravel_sections(root, be)
        for k, v in laravel_sections.items():
            sections[k].extend(v)
        route_summary = extract_route_summary(be)

    # Next.js
    if stack["nextjs"] and stack["frontend_root"]:
        fe = stack["frontend_root"]
        nextjs_sections = build_nextjs_sections(root, fe)
        for k, v in nextjs_sections.items():
            sections[k].extend(v)

    # Vue / Nuxt (reuse nextjs scanner with adjusted labels)
    if (stack["vue"] or stack["nuxt"]) and stack["frontend_root"] and not stack["nextjs"]:
        fe = stack["frontend_root"]
        vue_sections = build_nextjs_sections(root, fe)  # similar structure
        for k, v in vue_sections.items():
            sections[k].extend(v)

    # Pure Python
    if stack["python"] and not stack["laravel"]:
        py_root = stack["backend_root"] or root
        for f, rel in walk(py_root, {".py"}):
            label = label_file(rel)
            sections["Python Source"].append(format_line(rel, label))

    # Generic fallback
    if not any([stack["laravel"], stack["nextjs"], stack["vue"], stack["nuxt"], stack["python"]]):
        generic = build_generic_sections(root)
        for k, v in generic.items():
            sections[k].extend(v)

    write_index(root, stack, sections, entries, route_summary, verbose=args.verbose)

    # Inject CLAUDE.md hook (always, unless explicitly skipped)
    if not args.skip_claude_md:
        result = inject_claude_md(root)
        messages = {
            "created":         "✅ CLAUDE.md created with session-start hook",
            "injected":        "✅ CLAUDE.md updated — session-start hook injected",
            "updated":         "✅ CLAUDE.md updated — session-start hook refreshed",
            "already_present": "✔  CLAUDE.md already has session-start hook (no change)",
        }
        print(messages.get(result, f"   CLAUDE.md: {result}"))


if __name__ == "__main__":
    main()
