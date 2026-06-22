"""
Context Engine — workspace intelligence for Foder.

Responsibilities:
1. Project type detection (Python, Node, Go, Rust, Java, C/C++, Docker, etc.)
2. Build system, test framework, linter, formatter detection
3. Smart file selection — find relevant files without loading entire repos
4. Dependency / import tracing (best-effort, language-aware)
5. Git diff awareness — recently modified files surface first

Design:
- Zero mandatory extra dependencies (stdlib + already-installed packages).
- All operations are best-effort: never raise, always return something useful.
- Results are cached per workspace path to avoid redundant scans.
- Lazy: nothing runs until explicitly requested.
"""

import re
import subprocess
from pathlib import Path
from typing import NamedTuple
import foder.config as config


# ── Project Profile ────────────────────────────────────────────────────────────

class ProjectProfile(NamedTuple):
    """Everything detected about a project's tech stack."""
    project_type:   list[str]   # e.g. ["python", "fastapi"]
    package_manager: str        # pip / npm / cargo / go / maven / etc.
    test_framework:  str        # pytest / jest / go test / etc.
    build_system:    str        # make / cargo / gradle / tsc / vite / etc.
    linter:          str        # ruff / eslint / golangci-lint / clippy / etc.
    formatter:       str        # black / prettier / gofmt / rustfmt / etc.
    entry_points:    list[str]  # main.py / index.js / main.go / etc.
    config_files:    list[str]  # detected config files present
    docker:          bool
    summary:         str        # human-readable one-liner


# ── Detection helpers ─────────────────────────────────────────────────────────

def _has(ws: Path, *names: str) -> bool:
    return any((ws / n).exists() for n in names)


def _read_first(ws: Path, *names: str) -> str:
    for n in names:
        p = ws / n
        if p.exists():
            try:
                return p.read_text(encoding="utf-8", errors="replace")[:4096]
            except Exception:
                pass
    return ""


def _glob_any(ws: Path, *patterns: str) -> bool:
    for pat in patterns:
        if any(ws.glob(pat)):
            return True
    return False


# ── Workspace detection ───────────────────────────────────────────────────────

def _detect_project_uncached(ws: Path) -> ProjectProfile:

    types:        list[str] = []
    pkg_mgr:      str = "unknown"
    test_fw:      str = "unknown"
    build_sys:    str = "unknown"
    linter:       str = "none"
    formatter:    str = "none"
    entry_points: list[str] = []
    config_files: list[str] = []
    docker:       bool = False

    # ── Python ───────────────────────────────────────────────────────────────
    if _has(ws, "pyproject.toml", "setup.py", "setup.cfg", "requirements.txt", "Pipfile"):
        types.append("python")
        pkg_mgr = "pip"
        if _has(ws, "Pipfile"):
            pkg_mgr = "pipenv"
        if _has(ws, "pyproject.toml"):
            txt = _read_first(ws, "pyproject.toml")
            if "poetry" in txt:
                pkg_mgr = "poetry"
            if "uv" in txt:
                pkg_mgr = "uv"
            config_files.append("pyproject.toml")

        # Frameworks
        reqs = _read_first(ws, "requirements.txt", "pyproject.toml", "Pipfile")
        if any(f in reqs for f in ("fastapi", "uvicorn")):
            types.append("fastapi")
        if "flask" in reqs:
            types.append("flask")
        if "django" in reqs:
            types.append("django")
        if "streamlit" in reqs:
            types.append("streamlit")
        if any(f in reqs for f in ("pytest", "[tool.pytest")):
            test_fw = "pytest"
        elif any(f in reqs for f in ("unittest",)):
            test_fw = "unittest"
        else:
            test_fw = "pytest"  # default assumption for Python

        # Build
        if _has(ws, "Makefile"):
            build_sys = "make"
        if _has(ws, "pyproject.toml"):
            build_sys = "setuptools/build"

        # Linter/formatter
        if _has(ws, ".ruff.toml") or "ruff" in _read_first(ws, "pyproject.toml"):
            linter = "ruff"
        elif _has(ws, ".flake8") or _glob_any(ws, "**/.flake8"):
            linter = "flake8"
        if "black" in _read_first(ws, "pyproject.toml"):
            formatter = "black"
        elif "ruff" in linter:
            formatter = "ruff format"

        # Entry points
        for ep in ("main.py", "app.py", "run.py", "manage.py", "__main__.py"):
            if (ws / ep).exists():
                entry_points.append(ep)

    # ── JavaScript / TypeScript / Node ────────────────────────────────────────
    if _has(ws, "package.json"):
        types.append("nodejs")
        pkg_json = _read_first(ws, "package.json")
        pkg_mgr = "npm"
        if _has(ws, "yarn.lock"):
            pkg_mgr = "yarn"
        elif _has(ws, "pnpm-lock.yaml"):
            pkg_mgr = "pnpm"
        elif _has(ws, "bun.lockb"):
            pkg_mgr = "bun"
        config_files.append("package.json")

        # Framework detection
        if any(f in pkg_json for f in ('"react"', '"next"')):
            if '"next"' in pkg_json:
                types.append("nextjs")
            else:
                types.append("react")
        if '"vue"' in pkg_json:
            types.append("vue")
        if '"svelte"' in pkg_json:
            types.append("svelte")
        if '"express"' in pkg_json:
            types.append("express")

        # Test framework
        for fw, kw in [("jest", '"jest"'), ("vitest", '"vitest"'),
                       ("mocha", '"mocha"'), ("ava", '"ava"')]:
            if kw in pkg_json:
                test_fw = fw
                break

        # Build
        if '"vite"' in pkg_json:
            build_sys = "vite"
        elif '"webpack"' in pkg_json:
            build_sys = "webpack"
        elif '"tsc"' in pkg_json or _has(ws, "tsconfig.json"):
            build_sys = "tsc"
        else:
            build_sys = "npm scripts"

        # Linter/formatter
        if _has(ws, ".eslintrc", ".eslintrc.js", ".eslintrc.json", ".eslintrc.yaml"):
            linter = "eslint"
        elif '"eslint"' in pkg_json:
            linter = "eslint"
        if '"prettier"' in pkg_json or _has(ws, ".prettierrc", ".prettierrc.json"):
            formatter = "prettier"

        # TypeScript
        if _has(ws, "tsconfig.json") or '"typescript"' in pkg_json:
            if "typescript" not in types:
                types.append("typescript")

        for ep in ("index.js", "index.ts", "src/index.js", "src/index.ts",
                   "src/main.js", "src/main.ts", "app.js", "server.js"):
            if (ws / ep).exists():
                entry_points.append(ep)

    # ── Go ────────────────────────────────────────────────────────────────────
    if _has(ws, "go.mod"):
        types.append("go")
        pkg_mgr = "go modules"
        test_fw = "go test"
        build_sys = "go build"
        linter = "golangci-lint"
        formatter = "gofmt"
        config_files.append("go.mod")
        for ep in ("main.go", "cmd/main.go"):
            if (ws / ep).exists():
                entry_points.append(ep)

    # ── Rust ──────────────────────────────────────────────────────────────────
    if _has(ws, "Cargo.toml"):
        types.append("rust")
        pkg_mgr = "cargo"
        test_fw = "cargo test"
        build_sys = "cargo build"
        linter = "clippy"
        formatter = "rustfmt"
        config_files.append("Cargo.toml")
        for ep in ("src/main.rs", "src/lib.rs"):
            if (ws / ep).exists():
                entry_points.append(ep)

    # ── Java / Kotlin ─────────────────────────────────────────────────────────
    if _has(ws, "pom.xml"):
        types.append("java")
        pkg_mgr = "maven"
        test_fw = "junit"
        build_sys = "maven"
        config_files.append("pom.xml")
    if _has(ws, "build.gradle", "build.gradle.kts"):
        if "java" not in types:
            types.append("java")
        pkg_mgr = "gradle"
        build_sys = "gradle"
        if _has(ws, "build.gradle.kts") or _glob_any(ws, "**/*.kt"):
            if "kotlin" not in types:
                types.append("kotlin")

    # ── C / C++ ───────────────────────────────────────────────────────────────
    if _glob_any(ws, "*.c", "*.cpp", "*.h", "*.hpp"):
        types.append("c/c++")
        if _has(ws, "CMakeLists.txt"):
            build_sys = "cmake"
            config_files.append("CMakeLists.txt")
        elif _has(ws, "Makefile"):
            build_sys = "make"
        else:
            build_sys = "gcc/g++"

    # ── Docker ────────────────────────────────────────────────────────────────
    if _has(ws, "Dockerfile", "docker-compose.yml", "docker-compose.yaml"):
        docker = True
        config_files.extend(
            n for n in ("Dockerfile", "docker-compose.yml", "docker-compose.yaml")
            if (ws / n).exists()
        )

    # ── Makefile (generic) ────────────────────────────────────────────────────
    if _has(ws, "Makefile") and build_sys == "unknown":
        build_sys = "make"
        config_files.append("Makefile")

    if not types:
        types = ["unknown"]

    summary_parts = ["/".join(types)]
    if pkg_mgr != "unknown":
        summary_parts.append(f"pkg:{pkg_mgr}")
    if test_fw != "unknown":
        summary_parts.append(f"test:{test_fw}")
    if build_sys != "unknown":
        summary_parts.append(f"build:{build_sys}")
    if docker:
        summary_parts.append("docker")

    return ProjectProfile(
        project_type   = types,
        package_manager= pkg_mgr,
        test_framework = test_fw,
        build_system   = build_sys,
        linter         = linter,
        formatter      = formatter,
        entry_points   = entry_points,
        config_files   = config_files,
        docker         = docker,
        summary        = " · ".join(summary_parts),
    )


# ── Profile cache (avoids rescanning on every LLM iteration) ─────────────────

_profile_cache: dict[str, ProjectProfile] = {}
_summary_cache: dict[str, str] = {}


def detect_project(workspace: Path | None = None) -> ProjectProfile:
    """
    Detect the tech stack of the workspace.
    Result is cached per workspace path — re-detection only runs when the
    workspace directory changes (e.g. after `cd`).
    """
    ws  = workspace or config.WORKSPACE
    key = str(ws)
    if key not in _profile_cache:
        _profile_cache[key] = _detect_project_uncached(ws)
    return _profile_cache[key]


def invalidate_cache(workspace: Path | None = None) -> None:
    """Call this after `cd` so the next request rescans the new workspace."""
    ws  = workspace or config.WORKSPACE
    key = str(ws)
    _profile_cache.pop(key, None)
    _summary_cache.pop(key, None)


# ── Smart file selection ──────────────────────────────────────────────────────

# Files never relevant to surface automatically
_IGNORE_DIRS = {
    ".git", "__pycache__", "node_modules", ".venv", "venv", "env",
    "dist", "build", ".next", ".nuxt", "target", "vendor",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", "coverage",
    ".benchmarks", "htmlcov", ".tox",
}

_IGNORE_EXTS = {
    ".pyc", ".pyo", ".pyd", ".so", ".dll", ".dylib",
    ".jpg", ".jpeg", ".png", ".gif", ".svg", ".ico", ".webp",
    ".mp3", ".mp4", ".wav", ".avi", ".mov",
    ".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar",
    ".pdf", ".docx", ".xlsx", ".pptx",
    ".lock",   # lock files are huge and rarely needed
    ".min.js", ".min.css",
    ".map",
}

# Files that are always high-value context
_HIGH_VALUE_FILES = {
    "README.md", "README.rst", "README.txt",
    "pyproject.toml", "setup.py", "requirements.txt",
    "package.json", "go.mod", "Cargo.toml", "pom.xml", "build.gradle",
    "Makefile", "CMakeLists.txt",
    "Dockerfile", "docker-compose.yml",
    ".env.example", "foder.json",
    "CHANGELOG.md", "CONTRIBUTING.md",
}


def _should_index(p: Path) -> bool:
    """True if this file is worth indexing/surfacing."""
    if p.name.startswith("."):
        return False
    if any(part in _IGNORE_DIRS for part in p.parts):
        return False
    suffix = p.suffix.lower()
    if suffix in _IGNORE_EXTS:
        return False
    if p.name.endswith((".min.js", ".min.css", ".map")):
        return False
    if p.stat().st_size > config.MAX_AUTO_FILE_BYTES * 4:
        return False
    return True


def list_workspace_files(workspace: Path | None = None, max_files: int = 200) -> list[Path]:
    """
    Return a ranked list of workspace files, most relevant first.
    Ranking: high-value files > recently modified > alphabetical.
    """
    ws = workspace or config.WORKSPACE
    results: list[tuple[int, float, Path]] = []  # (priority, -mtime, path)

    try:
        for p in ws.rglob("*"):
            if not p.is_file():
                continue
            try:
                if not _should_index(p):
                    continue
                priority = 0 if p.name in _HIGH_VALUE_FILES else 1
                mtime    = p.stat().st_mtime
                results.append((priority, -mtime, p))
            except Exception:
                continue
    except Exception:
        return []

    results.sort()
    return [r[2] for r in results[:max_files]]


def find_relevant_files(
    query: str,
    workspace: Path | None = None,
    max_files: int = 10,
) -> list[Path]:
    """
    Find files most relevant to a natural-language query.

    Strategy (in order):
    1. Files whose path contains words from the query.
    2. Files recently modified (git-aware if possible).
    3. Entry point files.
    4. High-value config files.
    """
    ws    = workspace or config.WORKSPACE
    query_lower  = query.lower()
    query_tokens = set(re.findall(r"\w+", query_lower)) - {"the", "a", "an", "in",
                                                            "of", "to", "for", "with",
                                                            "and", "or", "it", "this",
                                                            "that", "is", "are", "was"}

    all_files = list_workspace_files(ws, max_files=500)

    scored: list[tuple[float, Path]] = []
    for p in all_files:
        score = 0.0
        name_lower = p.name.lower()
        rel_lower  = str(p.relative_to(ws)).lower()

        # Token match in path
        for tok in query_tokens:
            if tok in rel_lower:
                score += 2.0
            if tok in name_lower:
                score += 1.0

        # Extension match (e.g. "python" → .py files)
        lang_ext_map = {
            "python": ".py", "javascript": ".js", "typescript": ".ts",
            "rust": ".rs", "go": ".go", "java": ".java",
            "css": ".css", "html": ".html", "json": ".json",
            "yaml": ".yaml", "toml": ".toml", "shell": ".sh",
            "bash": ".sh", "c": ".c", "cpp": ".cpp",
        }
        for lang, ext in lang_ext_map.items():
            if lang in query_tokens and p.suffix == ext:
                score += 1.5

        # High-value file bonus
        if p.name in _HIGH_VALUE_FILES:
            score += 0.5

        # Recently modified bonus (last 24h)
        try:
            import time
            if (time.time() - p.stat().st_mtime) < 86400:
                score += 0.3
        except Exception:
            pass

        if score > 0:
            scored.append((score, p))

    scored.sort(key=lambda x: -x[0])
    top = [p for _, p in scored[:max_files]]

    # If we didn't find enough, pad with entry points + high-value files
    if len(top) < max_files:
        for p in all_files:
            if p not in top and (p.name in _HIGH_VALUE_FILES):
                top.append(p)
                if len(top) >= max_files:
                    break

    return top[:max_files]


def get_git_modified_files(workspace: Path | None = None) -> list[Path]:
    """Return files modified since the last git commit (best-effort)."""
    ws = workspace or config.WORKSPACE
    try:
        out = subprocess.check_output(
            ["git", "diff", "--name-only", "HEAD"],
            cwd=str(ws), stderr=subprocess.DEVNULL, timeout=3
        ).decode().strip()
        files = []
        for line in out.splitlines():
            p = (ws / line.strip()).resolve()
            if p.is_file():
                files.append(p)
        return files
    except Exception:
        return []


def build_context_summary(workspace: Path | None = None) -> str:
    """
    Build a compact workspace context string suitable for system-prompt injection.
    Cached per workspace path — git diff check is the only live call.
    """
    ws  = workspace or config.WORKSPACE
    key = str(ws)
    if key in _summary_cache:
        # Still refresh the git-modified-files part cheaply
        modified = get_git_modified_files(ws)
        if modified:
            names = [p.name for p in modified[:5]]
            # Patch the cached value with fresh git info rather than full rescan
            base = _summary_cache[key]
            # Strip old RECENTLY MODIFIED line and replace
            lines = [l for l in base.splitlines() if not l.startswith("RECENTLY MODIFIED:")]
            lines.append("RECENTLY MODIFIED: " + ", ".join(names))
            return "\n".join(lines)
        return _summary_cache[key]

    result = _build_context_summary_uncached(ws)
    _summary_cache[key] = result
    return result


def _build_context_summary_uncached(ws: Path) -> str:
    profile = detect_project(ws)

    lines: list[str] = [
        f"PROJECT: {profile.summary}",
        f"WORKSPACE: {ws}",
    ]

    if profile.entry_points:
        lines.append("ENTRY POINTS: " + ", ".join(profile.entry_points))

    if profile.config_files:
        lines.append("CONFIG FILES: " + ", ".join(profile.config_files))

    # File count (quick estimate — don't scan every file)
    try:
        py_count  = sum(1 for _ in ws.rglob("*.py") if ".venv" not in str(_) and "__pycache__" not in str(_))
        js_count  = sum(1 for _ in ws.rglob("*.js") if "node_modules" not in str(_))
        ts_count  = sum(1 for _ in ws.rglob("*.ts") if "node_modules" not in str(_))
        if py_count:  lines.append(f"Python files: {py_count}")
        if js_count:  lines.append(f"JS files: {js_count}")
        if ts_count:  lines.append(f"TS files: {ts_count}")
    except Exception:
        pass

    modified = get_git_modified_files(ws)
    if modified:
        names = [p.name for p in modified[:5]]
        lines.append("RECENTLY MODIFIED: " + ", ".join(names))

    if profile.test_framework != "unknown":
        lines.append(f"TEST FRAMEWORK: {profile.test_framework}")
    if profile.linter != "none":
        lines.append(f"LINTER: {profile.linter}")
    if profile.docker:
        lines.append("DOCKER: yes")

    return "\n".join(lines)
