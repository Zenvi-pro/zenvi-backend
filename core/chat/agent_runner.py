"""
Agent runner — builds a LangChain agent with the selected LLM and tools,
runs it, and delegates tool execution via a callback interface.

Ported from zenvi-core. All PyQt/Qt dependencies removed.
Tool execution is delegated back to the caller (frontend) via a ToolExecutor callback
when running in WebSocket mode, or executed locally for server-side-only tools.
"""

import json
import os
import time
from typing import List, Dict, Any, Optional, Callable

from logger import log
from core.chat.prompts import MAIN_SYSTEM_PROMPT

# Load .env
try:
    from dotenv import load_dotenv
    _root_env = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), ".env")
    if os.path.exists(_root_env):
        load_dotenv(dotenv_path=_root_env, override=False)
except Exception:
    pass


SYSTEM_PROMPT = MAIN_SYSTEM_PROMPT


class ToolExecutionRequest:
    """Represents a request to execute a tool (sent to frontend via WebSocket)."""

    def __init__(self, tool_name: str, tool_args: Dict[str, Any], call_id: str):
        self.tool_name = tool_name
        self.tool_args = tool_args
        self.call_id = call_id

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "tool_call",
            "tool_name": self.tool_name,
            "tool_args": self.tool_args,
            "call_id": self.call_id,
        }


class ToolExecutionResult:
    """Result returned from frontend after executing a tool."""

    def __init__(self, call_id: str, result: str, error: Optional[str] = None):
        self.call_id = call_id
        self.result = result
        self.error = error


# Type for the callback that executes tools on the frontend
ToolExecutorCallback = Callable[[ToolExecutionRequest], ToolExecutionResult]


def run_agent_with_tools(
    model_id: str,
    messages: List[Dict[str, Any]],
    tools: list,
    tool_executor: Optional[ToolExecutorCallback] = None,
    system_prompt: str = SYSTEM_PROMPT,
    max_iterations: int = 15,
    timeout_seconds: int = 120,
) -> str:
    """
    Run a LangChain agent with the given tools and system prompt.

    If tool_executor is provided, tool calls are delegated to it (e.g., sent to
    the frontend via WebSocket for timeline operations). Otherwise tools are
    invoked locally (server-side tools like search, generation, etc.).

    Returns the final response text.
    """
    start_time = time.time()

    try:
        from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
    except ImportError as e:
        log.error("LangChain import failed: %s", e)
        return "Error: LangChain not available."

    from core.llm import get_model

    llm = get_model(model_id)
    if not llm:
        return f"Error: Could not load model '{model_id}'. Check API keys."

    tools_by_name = {getattr(t, "name", str(t)): t for t in tools}

    # Build LangChain message list
    lc_messages = [SystemMessage(content=system_prompt)]
    for m in messages:
        role = m.get("role") or m.get("type", "")
        content = m.get("content", "") or ""
        if isinstance(content, list):
            content = content[0].get("text", "") if content else ""
        if role == "user":
            lc_messages.append(HumanMessage(content=content))
        elif role == "assistant" and content:
            lc_messages.append(AIMessage(content=content))

    if not any(isinstance(m, HumanMessage) for m in lc_messages):
        return "Error: No message to send."

    try:
        llm_with_tools = llm.bind_tools(tools)

        for iteration in range(max_iterations):
            elapsed = time.time() - start_time
            if elapsed > timeout_seconds:
                return f"Error: Agent timed out after {int(elapsed)} seconds."

            response = llm_with_tools.invoke(lc_messages)
            lc_messages.append(response)

            tool_calls = (
                getattr(response, "tool_calls", None)
                or getattr(response, "additional_kwargs", {}).get("tool_calls", [])
            )

            if not tool_calls:
                break

            for tc in tool_calls:
                name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", None)
                args = tc.get("args", {}) if isinstance(tc, dict) else getattr(tc, "args", {}) or {}
                tid = tc.get("id") if isinstance(tc, dict) else getattr(tc, "id", "") or ""
                if not isinstance(args, dict):
                    args = {}

                tool = tools_by_name.get(name)

                if tool_executor and name not in tools_by_name:
                    # Tool is on the frontend — delegate via callback
                    req = ToolExecutionRequest(name, args, tid)
                    resp = tool_executor(req)
                    result = resp.error if resp.error else resp.result
                elif tool_executor and _is_frontend_tool(name):
                    # Explicitly frontend tool — delegate
                    req = ToolExecutionRequest(name, args, tid)
                    resp = tool_executor(req)
                    result = resp.error if resp.error else resp.result
                elif tool:
                    try:
                        result = tool.invoke(args)
                    except Exception as e:
                        log.error("Tool %s failed: %s", name, e)
                        result = f"Error: {e}"
                else:
                    result = f"Error: unknown tool {name}"

                lc_messages.append(ToolMessage(content=str(result), tool_call_id=tid))

                # Terminal tools — return immediately
                _TERMINAL_TOOLS = {
                    "insert_vidu_v2v_clip_into_selected_clip_tool",
                    "generate_video_and_add_to_timeline_tool",
                    "generate_transition_clip_tool",
                    "generate_manim_video_tool",
                    "invoke_video_agent",
                }
                if name in _TERMINAL_TOOLS and not str(result).startswith("Error:"):
                    return str(result)

        # Final response
        for m in reversed(lc_messages):
            if isinstance(m, AIMessage):
                content = getattr(m, "content", None)
                if content and isinstance(content, str):
                    return content
                if content:
                    return str(content)
        return "Done."
    except Exception as e:
        log.error("Agent execution failed: %s", e, exc_info=True)
        return f"Error: {e}"


# Import the canonical set of frontend-delegated tool names
from core.tools.openshot import FRONTEND_TOOL_NAMES as _FRONTEND_TOOL_NAMES


def _is_frontend_tool(name: str) -> bool:
    """Check if a tool should be executed on the frontend."""
    return name in _FRONTEND_TOOL_NAMES


def run_agent(model_id, messages, tool_executor=None, timeout_seconds=120):
    """
    Run the LangChain agent with multi-agent root or single-agent fallback.
    """
    try:
        from core.agents.root_agent import run_root_agent
        return run_root_agent(model_id, messages, tool_executor, timeout_seconds)
    except Exception as e:
        log.debug("Multi-agent root not used: %s; falling back to single agent", e)

    from core.tools.voice_music_tools import get_voice_music_tools_for_langchain
    from core.tools.openshot import get_all_openshot_tools
    # All tools — openshot tools are delegated to frontend via tool_executor
    all_tools = get_voice_music_tools_for_langchain() + get_all_openshot_tools()

    return run_agent_with_tools(
        model_id=model_id,
        messages=messages,
        tools=all_tools,
        tool_executor=tool_executor,
        system_prompt=SYSTEM_PROMPT,
        timeout_seconds=timeout_seconds,
    )
