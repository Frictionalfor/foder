"""
Configuration — all runtime settings for Foder.
Priority: env var > foder.json > defaults.
"""

import os
import json as _json
from pathlib import Path

# ── Workspace ─────────────────────────────────────────────────────────────────

WORKSPACE: Path = Path(os.environ.get("FODER_WORKSPACE", Path.cwd())).resolve()

# ── Ollama ────────────────────────────────────────────────────────────────────

OLLAMA_BASE_URL: str = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL: str    = os.environ.get("OLLAMA_MODEL", "qwen2.5-coder:3b")


def _detect_default_model() -> str:
    """
    If the configured model is the factory default AND isn't actually installed,
    try to pick the first available Ollama model so the agent works out-of-the-box
    regardless of which model the user has pulled.
    Returns the best available model name, or the config value unchanged.
    """
    if os.environ.get("OLLAMA_MODEL"):
        return OLLAMA_MODEL          # user explicitly set it — respect it
    try:
        import httpx as _httpx
        timeout = _httpx.Timeout(connect=2.0, read=2.0, write=2.0, pool=2.0)
        resp = _httpx.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=timeout)
        models = [m["name"] for m in resp.json().get("models", [])]
        if not models:
            return OLLAMA_MODEL
        if OLLAMA_MODEL in models:
            return OLLAMA_MODEL      # configured model is available — use it
        _PREFERRED = [
            "qwen2.5-coder:32b", "qwen2.5-coder:14b", "qwen2.5-coder:7b",
            "qwen2.5-coder",
            "deepseek-coder:33b", "deepseek-coder:6.7b", "deepseek-coder",
            "codellama:34b", "codellama:13b", "codellama:7b", "codellama",
            "qwen3", "qwen2.5", "llama3", "mistral", "phi3",
        ]
        for pref in _PREFERRED:
            for m in models:
                if m.lower().startswith(pref):
                    return m
        return models[0]             # any model beats no model
    except Exception:
        return OLLAMA_MODEL

# ── Agent limits ──────────────────────────────────────────────────────────────

MAX_ITERATIONS: int  = int(os.environ.get("FODER_MAX_ITER", "20"))
SHELL_TIMEOUT: int   = int(os.environ.get("FODER_SHELL_TIMEOUT", "30"))
LLM_TIMEOUT: float   = float(os.environ.get("FODER_LLM_TIMEOUT", "600"))

# ── Custom instructions ───────────────────────────────────────────────────────

CUSTOM_INSTRUCTIONS: str = os.environ.get("FODER_INSTRUCTIONS", "")

# ── Feature flags ─────────────────────────────────────────────────────────────

# Enable local RAG indexing (requires sqlite3 + optional tree-sitter)
INDEXING_ENABLED: bool = os.environ.get("FODER_INDEXING", "0") == "1"

# Max file size loaded automatically by context engine (bytes)
MAX_AUTO_FILE_BYTES: int = int(os.environ.get("FODER_MAX_FILE_BYTES", str(32 * 1024)))

# Max files indexed per workspace scan
MAX_INDEX_FILES: int = int(os.environ.get("FODER_MAX_INDEX_FILES", "500"))

# ── Paths ─────────────────────────────────────────────────────────────────────

USER_DIR: Path   = Path.home() / ".foder"
PREFS_FILE: Path = USER_DIR / "preferences.json"
THEME_FILE: Path = USER_DIR / "theme.json"
LOG_FILE: Path   = USER_DIR / "audit.log"
HISTORY_FILE: Path = USER_DIR / "history.jsonl"
TEMPLATES_DIR: Path = USER_DIR / "templates"


def load_project_config() -> None:
    """
    Load foder.json from WORKSPACE if it exists.
    Values override defaults; env vars always take precedence.
    Also auto-detects the best available Ollama model on first call.
    """
    global OLLAMA_MODEL, OLLAMA_BASE_URL, MAX_ITERATIONS
    global SHELL_TIMEOUT, LLM_TIMEOUT, CUSTOM_INSTRUCTIONS, INDEXING_ENABLED

    # Auto-detect best available model if still at factory default
    if not os.environ.get("OLLAMA_MODEL"):
        OLLAMA_MODEL = _detect_default_model()

    cfg_path = WORKSPACE / "foder.json"
    if not cfg_path.exists():
        return

    try:
        data = _json.loads(cfg_path.read_text(encoding="utf-8"))
    except Exception:
        return  # malformed — silently skip

    if not os.environ.get("OLLAMA_MODEL"):
        OLLAMA_MODEL = data.get("model", OLLAMA_MODEL)
    if not os.environ.get("OLLAMA_BASE_URL"):
        OLLAMA_BASE_URL = data.get("ollama_url", OLLAMA_BASE_URL)
    if not os.environ.get("FODER_MAX_ITER"):
        MAX_ITERATIONS = int(data.get("max_iterations", MAX_ITERATIONS))
    if not os.environ.get("FODER_SHELL_TIMEOUT"):
        SHELL_TIMEOUT = int(data.get("shell_timeout", SHELL_TIMEOUT))
    if not os.environ.get("FODER_LLM_TIMEOUT"):
        LLM_TIMEOUT = float(data.get("llm_timeout", LLM_TIMEOUT))
    if not os.environ.get("FODER_INSTRUCTIONS"):
        CUSTOM_INSTRUCTIONS = data.get("instructions", CUSTOM_INSTRUCTIONS)
    if not os.environ.get("FODER_INDEXING"):
        INDEXING_ENABLED = bool(data.get("indexing", INDEXING_ENABLED))


def load_user_preferences() -> dict:
    """Load ~/.foder/preferences.json. Returns {} if missing or malformed."""
    try:
        if PREFS_FILE.exists():
            return _json.loads(PREFS_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def save_user_preferences(prefs: dict) -> None:
    """Persist user preferences to ~/.foder/preferences.json."""
    try:
        USER_DIR.mkdir(parents=True, exist_ok=True)
        PREFS_FILE.write_text(_json.dumps(prefs, indent=2), encoding="utf-8")
    except Exception:
        pass
