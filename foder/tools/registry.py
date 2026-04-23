"""
Tool registry — maps tool names to their execute functions and schemas.
All tool calls are dispatched through here.
"""

import foder.tools.file_read as file_read
import foder.tools.file_write as file_write
import foder.tools.dir_list as dir_list
import foder.tools.dir_create as dir_create
import foder.tools.shell_exec as shell_exec

# Map: tool_name -> module
_REGISTRY = {
    "file_read":  file_read,
    "file_write": file_write,
    "dir_list":   dir_list,
    "dir_create": dir_create,
    "shell_exec": shell_exec,
}

# Exported schemas for prompt injection
TOOL_SCHEMAS: list[dict] = [mod.SCHEMA for mod in _REGISTRY.values()]


def dispatch(tool_name: str, parameters: dict) -> str:
    """
    Validate and execute a tool call.
    Returns a string result (always — errors are returned as strings too).
    """
    if tool_name not in _REGISTRY:
        return f"[error] Unknown tool: '{tool_name}'"

    module = _REGISTRY[tool_name]
    schema = module.SCHEMA
    required = schema.get("required", [])

    for key in required:
        if key not in parameters:
            return f"[error] Missing required parameter '{key}' for tool '{tool_name}'"

    try:
        return module.execute(**{k: parameters[k] for k in parameters})
    except TypeError as e:
        return f"[error] Invalid parameters for tool '{tool_name}': {e}"
    except Exception as e:
        return f"[error] Tool '{tool_name}' raised an exception: {e}"
