"""
Skills System — reusable, loadable capability bundles for Foder.

Skills are JSON files stored in:
  <workspace>/skills/     — project-level skills
  ~/.foder/skills/        — user-level skills
  <foder_package>/skills/ — built-in skills (shipped with Foder)

Each skill contains:
  name, description, tags, intent_keywords,
  steps, best_practices, templates,
  system_prompt_injection

The agent uses skills in two ways:
1. Auto-detection: matches user intent against skill keywords, loads automatically.
2. Manual: user runs /skills use <name> to load a skill explicitly.

When a skill is loaded, its system_prompt_injection is prepended to the user
message. This keeps the existing agent loop unchanged — skills are just
structured context injection.
"""

import json
from pathlib import Path
from typing import Any
import foder.config as config


# ── Skill paths ───────────────────────────────────────────────────────────────

def _skill_dirs() -> list[Path]:
    """Return all skill search paths in priority order (highest first)."""
    dirs = []
    # Workspace-level skills (highest priority)
    dirs.append(config.WORKSPACE / "skills")
    # User-level skills
    dirs.append(config.USER_DIR / "skills")
    # Built-in skills (shipped with the package)
    dirs.append(Path(__file__).parent.parent / "skills")
    return dirs


# ── Load / list skills ────────────────────────────────────────────────────────

def load_skill(name: str) -> dict | None:
    """
    Load a skill by name. Searches all skill dirs, returns first match.
    Returns None if not found.
    """
    for d in _skill_dirs():
        p = d / f"{name}.json"
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue
    return None


def list_skills() -> list[dict]:
    """
    Return all available skills (deduped by name, highest-priority wins).
    """
    seen: set[str] = set()
    skills: list[dict] = []
    for d in _skill_dirs():
        if not d.exists():
            continue
        for p in sorted(d.glob("*.json")):
            try:
                skill = json.loads(p.read_text(encoding="utf-8"))
                name  = skill.get("name", p.stem)
                if name not in seen:
                    seen.add(name)
                    skill["_source"] = str(p)
                    skills.append(skill)
            except Exception:
                continue
    return skills


def skills_summary() -> str:
    """Human-readable summary of all available skills for /skills list."""
    skills = list_skills()
    if not skills:
        return "No skills found.\n\nAdd skill JSON files to:\n  ~/.foder/skills/\n  <workspace>/skills/"

    lines = [f"{'NAME':<24} {'DESCRIPTION':<50} SOURCE"]
    lines.append("─" * 90)
    for s in skills:
        src = "built-in" if "foder/skills" in s.get("_source","") else \
              "user"     if ".foder/skills" in s.get("_source","") else "workspace"
        lines.append(f"{s.get('name','?'):<24} {s.get('description','')[:48]:<50} [{src}]")
    return "\n".join(lines)


# ── Intent detection ──────────────────────────────────────────────────────────

def detect_skill(user_input: str) -> dict | None:
    """
    Auto-detect the best skill for a user request based on intent_keywords.

    Returns the skill dict if a match is found with high enough confidence,
    else None (agent runs without a skill).

    Scoring:
    - Each matched keyword scores 1 point.
    - Exact phrase match scores 3 points.
    - Skill with highest score wins if score >= 2.
    """
    text   = user_input.lower()
    skills = list_skills()
    best_score = 0
    best_skill = None

    for skill in skills:
        score = 0
        for kw in skill.get("intent_keywords", []):
            kw_lower = kw.lower()
            if kw_lower in text:
                score += 3 if " " in kw_lower else 1  # phrase match scores more
        if score > best_score:
            best_score = score
            best_skill = skill

    if best_score >= 2:
        return best_skill
    return None


# ── Skill injection ───────────────────────────────────────────────────────────

def inject_skill(user_input: str, skill: dict) -> str:
    """
    Prepend skill instructions to the user's message.
    The agent loop receives this as the user turn — no changes needed to agent.py.
    """
    injection = skill.get("system_prompt_injection", "")
    if not injection:
        return user_input

    steps = skill.get("steps", [])
    practices = skill.get("best_practices", [])

    parts = [
        f"[SKILL: {skill['name']}]",
        f"{injection}",
    ]
    if steps:
        parts.append("\nREQUIRED STEPS (follow in order):")
        for i, step in enumerate(steps, 1):
            parts.append(f"  {i}. {step}")
    if practices:
        parts.append("\nBEST PRACTICES (apply these):")
        for p in practices:
            parts.append(f"  • {p}")

    parts.append(f"\nUSER REQUEST: {user_input}")
    return "\n".join(parts)


def apply_skill_auto(user_input: str) -> tuple[str, dict | None]:
    """
    Auto-detect a matching skill and inject it into the user input.

    Returns (modified_input, skill_used).
    If no skill matched, returns (original_input, None).
    """
    skill = detect_skill(user_input)
    if skill is None:
        return user_input, None
    return inject_skill(user_input, skill), skill


# ── /build_project mode ───────────────────────────────────────────────────────

_BUILD_PROJECT_PROMPT = """\
[PROJECT GENERATION MODE]

You are a full-stack engineering agent. Your ONLY job is to materialize the requested project by emitting tool calls.

HARD RULES:
- Do NOT explain, summarize, apologize, or tutor. No sentences at all.
- Do NOT say "I cannot build websites" — you can, via tools.
- Every action is a tool call: file_write, dir_create, shell_exec.
- If a file is long, write it in full anyway.
- If verification fails, fix the file and re-verify.
- If you have nothing left to do, output nothing more.

WORKFLOW (execute via tool calls):
1. Create directory structure with dir_create.
2. Write every file with file_write — complete code, no placeholders, no TODOs.
3. Run npm install / pip install / go mod tidy / etc with shell_exec.
4. Run the project build/test with shell_exec.
5. If it fails, read the error, repair files with file_edit, re-run verification.

USER REQUEST: {request}
"""


def build_project_prompt(request: str) -> str:
    """
    Return the full /build_project prompt for a given request.
    Also auto-detects and injects a matching skill if available.
    """
    skill = detect_skill(request)

    parts: list[str] = [
        "[PROJECT GENERATION MODE]",
        "",
        "You are an engineering agent. Build the requested project by emitting tool calls ONLY.",
        "",
        "HARD RULES:",
        "- Do NOT explain, summarize, apologize, or tutor. No sentences at all.",
        "- Do NOT say 'I cannot build websites'. You build via tools.",
        "- Every action is a tool call: file_write, dir_create, shell_exec.",
        "- Write COMPLETE files. No placeholders, no '// TODO', no 'pass'.",
        "- After writing files, run npm install and npm run build.",
        "- Fix any errors. Re-verify.",
        "",
        f"USER REQUEST: {request}",
    ]

    if skill:
        steps_text = "\n".join(f"  {i+1}. {s}" for i, s in enumerate(skill.get("steps", [])))
        practices_text = "\n".join(f"  • {p}" for p in skill.get("best_practices", []))
        parts.append("")
        parts.append(f"[SKILL LOADED: {skill['name']}]")
        parts.append(f"{skill.get('description','')}")
        parts.append("")
        parts.append("FOLLOW THESE STEPS IN ORDER (each is a tool call):")
        parts.append(steps_text)
        parts.append("")
        if practices_text:
            parts.append("BEST PRACTICES:")
            parts.append(practices_text)
            parts.append("")

        templates = skill.get("templates", {})
        if templates:
            parts.append("USE THESE TEMPLATES VERBATIM WHERE APPLICABLE:")
            for path, content in templates.items():
                parts.append("")
                parts.append(f"TEMPLATE: {path}")
                parts.append(content)

    return "\n".join(parts)
