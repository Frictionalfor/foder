"""
Tool registry — central dispatch for all Foder tools.

Tools are organized into categories:
  FILE     - read, write, edit, rename, delete
  DIR      - list, create, remove
  SEARCH   - grep_search
  SHELL    - shell_exec
  GIT      - git_tool

All tools share a common interface:
  - SCHEMA dict  (name, description, parameters, required)
  - execute(**kwargs) -> str

Dispatch is case-insensitive and supports model aliases so
different Ollama models that emit slightly different tool names
are handled transparently.
"""

import foder.tools.file_read   as file_read
import foder.tools.file_write  as file_write
import foder.tools.file_edit   as file_edit
import foder.tools.file_delete as file_delete
import foder.tools.file_rename as file_rename
import foder.tools.dir_list    as dir_list
import foder.tools.dir_create  as dir_create
import foder.tools.dir_remove  as dir_remove
import foder.tools.shell_exec  as shell_exec
import foder.tools.grep_search as grep_search
import foder.tools.git_tool    as git_tool

# ── Primary registry ──────────────────────────────────────────────────────────

_REGISTRY: dict[str, object] = {
    # File tools
    "file_read":    file_read,
    "file_write":   file_write,
    "file_edit":    file_edit,
    "file_delete":  file_delete,
    "file_rename":  file_rename,
    # Directory tools
    "dir_list":     dir_list,
    "dir_create":   dir_create,
    "dir_remove":   dir_remove,
    # Search tools
    "grep_search":  grep_search,
    # Shell tool
    "shell_exec":   shell_exec,
    # Git tool
    "git_tool":     git_tool,
}

# ── Aliases — models sometimes use different names ────────────────────────────

_ALIASES: dict[str, str] = {
    # file_read
    "read_file":         "file_read",
    "read":              "file_read",
    # file_write
    "file_create":       "file_write",
    "write_file":        "file_write",
    "create_file":       "file_write",
    "write":             "file_write",
    # file_edit
    "edit_file":         "file_edit",
    "patch_file":        "file_edit",
    "str_replace":       "file_edit",
    "replace_in_file":   "file_edit",
    # file_delete
    "delete_file":       "file_delete",
    "remove_file":       "file_delete",
    "rm_file":           "file_delete",
    # file_rename
    "rename_file":       "file_rename",
    "move_file":         "file_rename",
    # dir_list
    "list_dir":          "dir_list",
    "ls":                "dir_list",
    "list_files":        "dir_list",
    # dir_create
    "mkdir":             "dir_create",
    "create_dir":        "dir_create",
    "make_dir":          "dir_create",
    # dir_remove
    "rmdir":             "dir_remove",
    "remove_dir":        "dir_remove",
    # shell_exec
    "bash":              "shell_exec",
    "run":               "shell_exec",
    "exec":              "shell_exec",
    "run_command":       "shell_exec",
    "execute_command":   "shell_exec",
    # grep_search
    "grep":              "grep_search",
    "search":            "grep_search",
    "ripgrep":           "grep_search",
    "find_in_files":     "grep_search",
    # git_tool
    "git":               "git_tool",
    "git_status":        "git_tool",
    "git_diff":          "git_tool",
    "git_commit":        "git_tool",
    "git_log":           "git_tool",
}


def _resolve(name: str) -> str | None:
    """Resolve a tool name (or alias) to the canonical name."""
    n = name.strip().lower()
    if n in _REGISTRY:
        return n
    if n in _ALIASES:
        canonical = _ALIASES[n]
        if canonical in _REGISTRY:
            return canonical
    return None


# Exported schemas for prompt injection
# Only expose the core tools to keep the system prompt lean.
_PROMPT_TOOLS = [
    "file_read", "file_write", "file_edit",
    "dir_list", "dir_create",
    "shell_exec", "grep_search", "git_tool",
]

TOOL_SCHEMAS: list[dict] = [
    _REGISTRY[name].SCHEMA  # type: ignore[attr-defined]
    for name in _PROMPT_TOOLS
    if name in _REGISTRY
]


def dispatch(tool_name: str, parameters: dict) -> str:
    """
    Validate and execute a tool call.
    Always returns a string — errors are returned as strings so the agent
    can read and react to them rather than crashing.
    """
    canonical = _resolve(tool_name)
    if canonical is None:
        return f"[error] Unknown tool: '{tool_name}'. Available: {', '.join(sorted(_REGISTRY))}"

    module   = _REGISTRY[canonical]
    schema   = module.SCHEMA  # type: ignore[attr-defined]
    required = schema.get("required", [])

    for key in required:
        if key not in parameters:
            return (
                f"[error] Missing required parameter '{key}' "
                f"for tool '{canonical}'"
            )

    try:
        result = module.execute(  # type: ignore[attr-defined]
            **{k: parameters[k] for k in parameters if k in schema.get("parameters", {})}
        )
    except TypeError as e:
        result = f"[error] Invalid parameters for tool '{canonical}': {e}"
    except Exception as e:
        result = f"[error] Tool '{canonical}' raised an exception: {type(e).__name__}: {e}"

    return result


def list_tools() -> list[str]:
    """Return sorted list of all available tool names (including aliases)."""
    return sorted(set(list(_REGISTRY.keys()) + list(_ALIASES.keys())))


def get_schema(tool_name: str) -> dict | None:
    """Return the schema for a tool, or None if not found."""
    canonical = _resolve(tool_name)
    if canonical is None:
        return None
    return _REGISTRY[canonical].SCHEMA  # type: ignore[attr-defined]
