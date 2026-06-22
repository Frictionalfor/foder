"""
CLI system for Foder — handles lifecycle flags.

  foder -h / --help       → structured help output
  foder --update          → pull latest from GitHub, preserve user data
  foder --uninstall       → remove foder, keep user projects and Ollama

All operations respect the local-first philosophy:
- Updates pull from https://github.com/Frictionalfor/foder only
- Install/uninstall never touches Ollama or user projects
- User data (~/.foder/) is preserved across updates
"""

import sys
import os
import subprocess
import shutil
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.rule import Rule
from rich import box

console = Console(highlight=False)

_DIM  = "#6B7280"
_GRN  = "#4ADE80"
_CYN  = "#06B6D4"
_YLW  = "#F59E0B"
_RED  = "#fca5a5"
_BLD  = "bold"

GITHUB_REPO = "https://github.com/Frictionalfor/foder"


# ── Help ──────────────────────────────────────────────────────────────────────

def show_help() -> None:
    console.print()
    console.print(Panel(
        Text.assemble(
            ("  ███████  ██████  ██████  ███████ ██████\n", f"bold {_GRN}"),
            ("  ██      ██    ██ ██   ██ ██      ██   ██\n", _GRN),
            ("  █████   ██    ██ ██   ██ █████   ██████ \n", _GRN),
            ("  ██      ██    ██ ██   ██ ██      ██   ██\n", _GRN),
            ("  ██       ██████  ██████  ███████ ██   ██", _GRN),
        ),
        border_style="#166534", padding=(0, 1),
        title=f"[{_DIM}]local AI coding agent[/{_DIM}]",
        subtitle=f"[{_DIM}]v0.2.0 · no cloud · no keys · just code[/{_DIM}]",
    ))

    # Usage
    console.print(f"  [{_BLD}]USAGE[/{_BLD}]")
    console.print()
    _row("foder",                   "start interactive REPL")
    _row('foder "your prompt"',     "single prompt, non-interactive")
    _row("foder init",              "interactive project setup wizard")
    _row("foder -h / --help",       "show this help")
    _row("foder --update",          "update to latest version")
    _row("foder --uninstall",       "remove foder from this machine")
    _row("foder --timeout <secs>",  "override LLM timeout for this session")
    console.print()

    # Agent modes
    console.print(f"  [{_BLD}]AGENT MODES[/{_BLD}]  [{_DIM}](slash commands inside REPL)[/{_DIM}]")
    console.print()
    _section([
        ("/plan <request>",       "plan implementation before executing"),
        ("/build <description>",  "generate a complete project end-to-end"),
        ("/auto <task>",          "autonomous mode — agent works independently"),
        ("/chat <question>",      "lightweight Q&A — no tools, fast responses"),
        ("/test [path]",          "auto-detect and run the project test suite"),
        ("/refactor <file>",      "targeted refactor using diff-based edits only"),
        ("/review [path]",        "code review a file or directory"),
        ("/explain <file>",       "explain code  [beginner|advanced]"),
        ("/watch [pattern]",      "watch files and trigger agent on save"),
        ("/compress",             "summarize + compress conversation context"),
    ])

    # Skills
    console.print(f"  [{_BLD}]SKILLS SYSTEM[/{_BLD}]")
    console.print()
    _section([
        ("/skills list",          "list all available skills"),
        ("/skills show <name>",   "show skill details and steps"),
        ("/skills use <name>",    "load a skill for the next request"),
        ("/skills detect <text>", "show which skill would match a request"),
    ])
    console.print(f"  [{_DIM}]  Skills auto-detect from your request. Add custom skills to:[/{_DIM}]")
    console.print(f"  [{_CYN}]  ~/.foder/skills/  or  ./skills/[/{_CYN}]")
    console.print()

    # History + Diagnostics
    console.print(f"  [{_BLD}]HISTORY + DIAGNOSTICS[/{_BLD}]")
    console.print()
    _section([
        ("/history [query]",      "search persistent prompt history"),
        ("/doctor",               "system health check (Python, Ollama, PATH, models)"),
        ("/audit [n]",            "recent tool call log"),
        ("/cost",                 "session stats (~tokens, tool calls, files written)"),
    ])

    # Workspace commands
    console.print(f"  [{_BLD}]WORKSPACE[/{_BLD}]")
    console.print()
    _section([
        ("/context",              "show detected project type (React, FastAPI, etc.)"),
        ("/memory add <fact>",    "remember a project fact"),
        ("/memory show",          "show all workspace memory"),
        ("/memory clear",         "clear workspace memory"),
        ("/index",                "list workspace files ranked by relevance"),
        ("/snapshot",             "save workspace file state"),
        ("/snapshot diff",        "show what changed since last snapshot"),
    ])

    # Session
    console.print(f"  [{_BLD}]SESSION[/{_BLD}]")
    console.print()
    _section([
        ("/models",               "list available Ollama models"),
        ("/switch [model]",       "switch model mid-session"),
        ("/model",                "show active model + RAM/capability info"),
        ("/theme",                "pick color theme (6 built-in)"),
        ("/clear",                "clear screen and conversation history"),
        ("/cost",                 "show session stats (~tokens, tool calls)"),
        ("/pin <file>",           "pin file to every prompt automatically"),
        ("/undo",                 "revert last file write"),
        ("/diff",                 "show diff of last file write"),
        ("/git",                  "show git status, branch, recent commits"),
        ("/audit [n]",            "show recent tool call audit log"),
        ("/arch",                 "show Foder architecture diagram"),
        ("/help",                 "show this help inside REPL"),
        ("/exit",                 "quit (unloads model from RAM)"),
    ])

    # Shortcuts
    console.print(f"  [{_BLD}]SHORTCUTS[/{_BLD}]")
    console.print()
    _section([
        ("! <cmd>",               "run a shell command"),
        ("!!",                    "re-run last shell command"),
        ("@filename",             "inject file content into prompt"),
        ("cd / ls / git / ...",   "common shell commands work directly"),
        ("\\ at end of line",     "continue input on next line (multi-line)"),
    ])

    # Environment
    console.print(f"  [{_BLD}]ENVIRONMENT VARIABLES[/{_BLD}]")
    console.print()
    _section([
        ("OLLAMA_MODEL",          "model to use  (default: qwen2.5-coder:3b)"),
        ("OLLAMA_BASE_URL",       "Ollama endpoint  (default: http://localhost:11434)"),
        ("FODER_WORKSPACE",       "workspace root  (default: current directory)"),
        ("FODER_MAX_ITER",        "max agent iterations  (default: 20)"),
        ("FODER_LLM_TIMEOUT",     "LLM request timeout seconds  (default: 600)"),
        ("FODER_SHELL_TIMEOUT",   "shell command timeout seconds  (default: 30)"),
        ("FODER_INSTRUCTIONS",    "custom instructions appended to system prompt"),
    ])

    # Per-project config
    console.print(f"  [{_BLD}]PROJECT CONFIG  [/{_BLD}][{_DIM}](foder.json in workspace root)[/{_DIM}]")
    console.print()
    console.print(f"  [{_CYN}]{{[/{_CYN}]")
    for k, v in [
        ('"model"',          '"qwen2.5-coder:7b"'),
        ('"instructions"',   '"This project uses FastAPI and PostgreSQL."'),
        ('"max_iterations"', '15'),
        ('"llm_timeout"',    '300'),
    ]:
        console.print(f"  [{_CYN}]  {k}: {v}[/{_CYN}]")
    console.print(f"  [{_CYN}]}}[/{_CYN}]")
    console.print()

    # Links
    console.print(f"  [{_BLD}]LINKS[/{_BLD}]")
    console.print()
    _section([
        ("GitHub",        GITHUB_REPO),
        ("Website",       "https://foder.vercel.app"),
        ("Install",       "https://foder.vercel.app/install.sh"),
        ("Issues",        f"{GITHUB_REPO}/issues"),
    ])
    console.print()

    # Source of truth
    console.print(f"  [{_BLD}]OFFICIAL SOURCES[/{_BLD}]")
    console.print()
    console.print(f"  [{_DIM}]  Install source:[/{_DIM}]  [{_CYN}]https://foder.vercel.app[/{_CYN}]")
    console.print(f"  [{_DIM}]  Update source: [/{_DIM}]  [{_CYN}]{GITHUB_REPO}[/{_CYN}]")
    console.print()


def _row(cmd: str, desc: str) -> None:
    t = Text()
    t.append(f"  {cmd:<32}", style=f"bold {_GRN}")
    t.append(desc, style=_DIM)
    console.print(t)


def _section(rows: list[tuple[str, str]]) -> None:
    for cmd, desc in rows:
        t = Text()
        t.append(f"  {cmd:<32}", style=_CYN)
        t.append(desc, style=_DIM)
        console.print(t)
    console.print()


# ── Update ────────────────────────────────────────────────────────────────────

def do_update() -> None:
    console.print()
    console.print(Panel(
        f"[bold {_GRN}]Foder Update[/bold {_GRN}]\n\n"
        f"[{_DIM}]Source: {GITHUB_REPO}[/{_DIM}]\n"
        f"[{_DIM}]User data in ~/.foder/ will be preserved.[/{_DIM}]",
        border_style="#166534", padding=(0, 1),
    ))
    console.print()

    # Confirm
    try:
        reply = input("  Update now? [Y/n] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        console.print(f"\n  [{_DIM}]cancelled[/{_DIM}]")
        return
    if reply not in ("", "y", "yes"):
        console.print(f"  [{_DIM}]cancelled[/{_DIM}]")
        return

    console.print()

    # Find the foder package directory
    foder_pkg = Path(__file__).parent.parent
    is_git_repo = (foder_pkg / ".git").exists()

    # Backup user data before update
    user_dir   = Path.home() / ".foder"
    backup_dir = Path.home() / ".foder_backup_update"
    _backup_user_data(user_dir, backup_dir)

    if is_git_repo:
        _update_via_git(foder_pkg, backup_dir)
    else:
        _update_via_pip(backup_dir)


def _backup_user_data(user_dir: Path, backup_dir: Path) -> None:
    """Backup ~/.foder to a temporary location before update."""
    if not user_dir.exists():
        return
    try:
        if backup_dir.exists():
            shutil.rmtree(backup_dir)
        shutil.copytree(user_dir, backup_dir)
        console.print(f"  [{_GRN}]✓[/{_GRN}]  User data backed up")
    except Exception as e:
        console.print(f"  [{_YLW}]![/{_YLW}]  Could not backup user data: {e}")


def _restore_user_data(backup_dir: Path, user_dir: Path) -> None:
    """Restore user data from backup."""
    if not backup_dir.exists():
        return
    try:
        # Merge: only restore files that existed before, don't wipe new ones
        for src in backup_dir.rglob("*"):
            if src.is_file():
                rel  = src.relative_to(backup_dir)
                dest = user_dir / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)
        console.print(f"  [{_GRN}]✓[/{_GRN}]  User data restored")
    except Exception as e:
        console.print(f"  [{_YLW}]![/{_YLW}]  Could not restore user data: {e}")


def _update_via_git(repo_dir: Path, backup_dir: Path) -> None:
    console.print(f"  [{_DIM}]→ pulling latest commits from GitHub...[/{_DIM}]")

    # Stash any local changes so pull doesn't fail
    _run(["git", "stash"], cwd=repo_dir, silent=True)

    ok = _run(["git", "pull", "--rebase", "origin", "main"], cwd=repo_dir)
    if not ok:
        ok = _run(["git", "pull", "origin", "main"], cwd=repo_dir)

    if not ok:
        console.print(f"  [{_RED}]✗  git pull failed. Rolling back.[/{_RED}]")
        _restore_user_data(backup_dir, Path.home() / ".foder")
        return

    console.print(f"  [{_GRN}]✓[/{_GRN}]  Code updated")
    console.print(f"  [{_DIM}]→ reinstalling package...[/{_DIM}]")

    pip_ok = _run([sys.executable, "-m", "pip", "install", "-e", ".", "-q",
                   "--break-system-packages"], cwd=repo_dir, silent=True)
    if not pip_ok:
        pip_ok = _run([sys.executable, "-m", "pip", "install", "-e", ".", "-q"],
                      cwd=repo_dir)

    _restore_user_data(backup_dir, Path.home() / ".foder")

    if pip_ok:
        console.print()
        console.print(f"  [{_GRN}]✓  Update complete![/{_GRN}]")
        console.print(f"  [{_DIM}]Restart foder to use the new version.[/{_DIM}]")
    else:
        console.print(f"  [{_RED}]✗  pip reinstall failed — foder may be broken. Run: pip install -e .[/{_RED}]")
    console.print()


def _update_via_pip(backup_dir: Path) -> None:
    console.print(f"  [{_DIM}]→ installing latest from GitHub...[/{_DIM}]")

    ok = _run([
        sys.executable, "-m", "pip", "install", "-q",
        f"git+{GITHUB_REPO}.git",
        "--break-system-packages",
    ], silent=True)
    if not ok:
        ok = _run([
            sys.executable, "-m", "pip", "install", "-q",
            f"git+{GITHUB_REPO}.git",
        ])

    _restore_user_data(backup_dir, Path.home() / ".foder")

    if ok:
        console.print(f"  [{_GRN}]✓  Update complete![/{_GRN}]")
        console.print(f"  [{_DIM}]Restart foder to use the new version.[/{_DIM}]")
    else:
        console.print(f"  [{_RED}]✗  Update failed. Try manually:[/{_RED}]")
        console.print(f"  [{_DIM}]git clone {GITHUB_REPO} && cd foder && pip install -e .[/{_DIM}]")
    console.print()


# ── Uninstall ─────────────────────────────────────────────────────────────────

def do_uninstall() -> None:
    console.print()
    console.print(Panel(
        f"[bold {_YLW}]Foder Uninstall[/bold {_YLW}]\n\n"
        f"[{_DIM}]This will remove:[/{_DIM}]\n"
        f"  • foder CLI binary\n"
        f"  • foder Python package\n"
        f"  • ~/.foder/ config and cache directory\n\n"
        f"[{_DIM}]This will NOT remove:[/{_DIM}]\n"
        f"  • Ollama\n"
        f"  • Your projects\n"
        f"  • Python\n"
        f"  • Any other software",
        border_style="#78350F", padding=(0, 1),
    ))
    console.print()

    try:
        reply = input("  Type 'yes' to confirm uninstall: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        console.print(f"\n  [{_DIM}]cancelled[/{_DIM}]")
        return

    if reply != "yes":
        console.print(f"  [{_DIM}]Uninstall cancelled. (type exactly 'yes' to confirm)[/{_DIM}]")
        return

    console.print()
    errors: list[str] = []

    # 1. Uninstall the Python package
    console.print(f"  [{_DIM}]→ removing foder package...[/{_DIM}]")
    ok = _run([sys.executable, "-m", "pip", "uninstall", "foder", "-y", "-q",
               "--break-system-packages"], silent=True)
    if not ok:
        ok = _run([sys.executable, "-m", "pip", "uninstall", "foder", "-y", "-q"])
    if ok:
        console.print(f"  [{_GRN}]✓[/{_GRN}]  Package removed")
    else:
        errors.append("pip uninstall failed — try: pip uninstall foder")
        console.print(f"  [{_YLW}]![/{_YLW}]  pip uninstall failed (may already be removed)")

    # 2. Remove ~/.foder config directory
    user_dir = Path.home() / ".foder"
    if user_dir.exists():
        try:
            # Offer to keep user data
            console.print()
            try:
                keep = input("  Keep ~/.foder/ (memory, preferences, history)? [Y/n] ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                keep = "y"
            if keep not in ("n", "no"):
                console.print(f"  [{_DIM}]  ~/.foder/ preserved[/{_DIM}]")
            else:
                shutil.rmtree(user_dir)
                console.print(f"  [{_GRN}]✓[/{_GRN}]  ~/.foder/ removed")
        except Exception as e:
            errors.append(f"Could not remove ~/.foder/: {e}")
            console.print(f"  [{_YLW}]![/{_YLW}]  Could not remove ~/.foder/: {e}")

    # 3. Remove any leftover bin/Scripts entry
    _remove_script_entry(errors)

    console.print()
    if not errors:
        console.print(f"  [{_GRN}]✓  Foder uninstalled successfully.[/{_GRN}]")
        console.print(f"  [{_DIM}]Ollama and your projects are untouched.[/{_DIM}]")
    else:
        console.print(f"  [{_YLW}]Uninstall completed with warnings:[/{_YLW}]")
        for e in errors:
            console.print(f"  [{_DIM}]  • {e}[/{_DIM}]")
    console.print()


def _remove_script_entry(errors: list[str]) -> None:
    """Best-effort removal of the foder script from bin/Scripts."""
    import shutil as _shutil
    foder_bin = _shutil.which("foder")
    if foder_bin:
        try:
            Path(foder_bin).unlink(missing_ok=True)
            console.print(f"  [{_GRN}]✓[/{_GRN}]  Binary removed: {foder_bin}")
        except PermissionError:
            errors.append(f"Could not remove {foder_bin} (permission denied — try sudo)")
        except Exception as e:
            errors.append(f"Could not remove binary: {e}")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _run(cmd: list[str], cwd: Path | None = None, silent: bool = False) -> bool:
    """Run a subprocess. Returns True on success."""
    try:
        result = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            capture_output=silent,
            timeout=120,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
        return False
