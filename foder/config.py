import os
from pathlib import Path
import json as _json

# Working directory — all file operations are scoped here
WORKSPACE: Path = Path(os.environ.get("FODER_WORKSPACE", Path.cwd())).resolve()

# Ollama settings
OLLAMA_BASE_URL: str = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL: str    = os.environ.get("OLLAMA_MODEL", "qwen2.5-coder:7b")

# Agent loop limits
MAX_ITERATIONS: int  = int(os.environ.get("FODER_MAX_ITER", "20"))

# Shell execution timeout (seconds)
SHELL_TIMEOUT: int   = int(os.environ.get("FODER_SHELL_TIMEOUT", "30"))

# LLM request timeout (seconds)
LLM_TIMEOUT: float   = float(os.environ.get("FODER_LLM_TIMEOUT", "300"))

# Custom system prompt suffix (injected at end of system prompt)
CUSTOM_INSTRUCTIONS: str = os.environ.get("FODER_INSTRUCTIONS", "")


def load_project_config() -> None:
    """
    Load foder.json from WORKSPACE if it exists.
    Values override env-var defaults but env vars take precedence over foder.json.
    Only reads — never writes — so memory impact is minimal.
    """
    global OLLAMA_MODEL, OLLAMA_BASE_URL, MAX_ITERATIONS
    global SHELL_TIMEOUT, LLM_TIMEOUT, CUSTOM_INSTRUCTIONS

    cfg_path = WORKSPACE / "foder.json"
    if not cfg_path.exists():
        return

    try:
        data = _json.loads(cfg_path.read_text(encoding="utf-8"))
    except Exception:
        return  # malformed — silently skip

    # Only apply if env var wasn't explicitly set
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
