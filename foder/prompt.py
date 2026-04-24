"""
Prompt builder — constructs the system prompt injected at the start of every session.
WORKSPACE is read dynamically so !cd changes are reflected in every new request.
"""

import json
import foder.config as config
from foder.tools.registry import TOOL_SCHEMAS

_TOOL_BLOCK = json.dumps(TOOL_SCHEMAS, indent=2)

_SYSTEM_TEMPLATE = """You are Foder, a coding agent. You write code to files. You do NOT explain or show code.

WORKSPACE: {workspace}
{git_context}
RULES:
- If asked to make/create/write a file → call file_write with the FULL working code immediately
- If asked to edit a file → call file_read then file_write
- If asked to list files → call dir_list
- If asked to run something → call shell_exec
- NEVER show code in your response — always write it to a file first
- NEVER explain steps — just act
- After writing files, respond with ONE short sentence

TOOL FORMAT:
{{"tool": "<name>", "parameters": {{...}}}}

{custom_instructions}TOOLS:
{tools}
"""


def build_messages(history: list[dict]) -> list[dict]:
    """Prepend a freshly built system prompt to the conversation history."""
    from foder.main import _get_git_context
    git = _get_git_context()
    git_line = f"GIT: {git}\n" if git else ""
    custom = f"PROJECT INSTRUCTIONS:\n{config.CUSTOM_INSTRUCTIONS}\n\n" if config.CUSTOM_INSTRUCTIONS else ""
    system_prompt = _SYSTEM_TEMPLATE.format(
        workspace=config.WORKSPACE,
        git_context=git_line,
        tools=_TOOL_BLOCK,
        custom_instructions=custom,
    )
    return [{"role": "system", "content": system_prompt}] + history
