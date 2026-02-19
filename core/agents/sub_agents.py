"""
Sub-agents: Video, Manim, Voice/Music.
Ported from zenvi-core; no Qt dependency.
"""

from logger import log
from core.chat.prompts import (
    VIDEO_AGENT_SYSTEM_PROMPT,
    MANIM_SYSTEM_PROMPT,
    VOICE_MUSIC_SYSTEM_PROMPT,
)


def run_video_agent(model_id, task_or_messages, tool_executor=None):
    """Run the Video/Timeline agent."""
    from core.chat.agent_runner import run_agent_with_tools

    if isinstance(task_or_messages, str):
        messages = [{"role": "user", "content": task_or_messages}]
    else:
        messages = list(task_or_messages)

    # Server-side tools (search, generation) + frontend tools delegated via tool_executor
    tools = _get_server_side_video_tools()
    return run_agent_with_tools(
        model_id=model_id,
        messages=messages,
        tools=tools,
        tool_executor=tool_executor,
        system_prompt=VIDEO_AGENT_SYSTEM_PROMPT,
    )


def run_manim_agent(model_id, task_or_messages, tool_executor=None):
    """Run the Manim agent."""
    from core.chat.agent_runner import run_agent_with_tools
    try:
        from core.tools.manim_tools import get_manim_tools_for_langchain
    except ImportError as e:
        log.debug("Manim tools not available: %s", e)
        return "Manim agent is not available."

    if isinstance(task_or_messages, str):
        messages = [{"role": "user", "content": task_or_messages}]
    else:
        messages = list(task_or_messages)

    tools = get_manim_tools_for_langchain()
    return run_agent_with_tools(
        model_id=model_id,
        messages=messages,
        tools=tools,
        tool_executor=tool_executor,
        system_prompt=MANIM_SYSTEM_PROMPT,
    )


def run_voice_music_agent(model_id, task_or_messages, tool_executor=None):
    """Run the Voice/Music agent."""
    from core.chat.agent_runner import run_agent_with_tools
    try:
        from core.tools.voice_music_tools import get_voice_music_tools_for_langchain
    except ImportError as e:
        log.debug("Voice/music tools not available: %s", e)
        return "Voice and music agent is not available."

    if isinstance(task_or_messages, str):
        messages = [{"role": "user", "content": task_or_messages}]
    else:
        messages = list(task_or_messages)

    tools = get_voice_music_tools_for_langchain()
    return run_agent_with_tools(
        model_id=model_id,
        messages=messages,
        tools=tools,
        tool_executor=tool_executor,
        system_prompt=VOICE_MUSIC_SYSTEM_PROMPT,
    )


def _get_server_side_video_tools():
    """Get all tools for the video agent (server-side + openshot frontend-delegated)."""
    tools = []
    try:
        from core.tools.search_tools import get_search_tools_for_langchain
        tools.extend(get_search_tools_for_langchain())
    except ImportError:
        pass
    try:
        from core.tools.generation_tools import get_generation_tools_for_langchain
        tools.extend(get_generation_tools_for_langchain())
    except ImportError:
        pass
    try:
        from core.tools.openshot import get_all_openshot_tools
        tools.extend(get_all_openshot_tools())
    except ImportError:
        pass
    return tools
