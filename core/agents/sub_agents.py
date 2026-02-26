"""
Sub-agents: Video, Manim, Voice/Music, Music, Transitions, Research, Product Launch.
Ported from zenvi-core; no Qt dependency.
"""

from logger import log
from core.chat.prompts import (
    VIDEO_AGENT_SYSTEM_PROMPT,
    MANIM_SYSTEM_PROMPT,
    VOICE_MUSIC_SYSTEM_PROMPT,
    MUSIC_SYSTEM_PROMPT,
    TRANSITIONS_SYSTEM_PROMPT,
    RESEARCH_SYSTEM_PROMPT,
    PRODUCT_LAUNCH_SYSTEM_PROMPT,
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
    # Add TTS tools for narration generation
    try:
        from core.tools.tts_tools import get_tts_tools_for_langchain
        tools.extend(get_tts_tools_for_langchain())
    except ImportError:
        pass
    return run_agent_with_tools(
        model_id=model_id,
        messages=messages,
        tools=tools,
        tool_executor=tool_executor,
        system_prompt=VOICE_MUSIC_SYSTEM_PROMPT,
    )


def run_music_agent(model_id, task_or_messages, tool_executor=None):
    """Run the Music agent (Suno) with OpenShot + Suno tools."""
    from core.chat.agent_runner import run_agent_with_tools
    from core.tools.music_tools import get_music_tools_for_langchain

    if isinstance(task_or_messages, str):
        messages = [{"role": "user", "content": task_or_messages}]
    else:
        messages = list(task_or_messages)

    tools = _get_server_side_video_tools()  # includes openshot tools for clip listing
    tools.extend(get_music_tools_for_langchain())
    return run_agent_with_tools(
        model_id=model_id,
        messages=messages,
        tools=tools,
        tool_executor=tool_executor,
        system_prompt=MUSIC_SYSTEM_PROMPT,
    )


def run_transitions_agent(model_id, task_or_messages, tool_executor=None):
    """Run the Transitions agent with transitions + clip-listing tools."""
    from core.chat.agent_runner import run_agent_with_tools
    from core.tools.openshot.transitions_tools import get_transitions_tools
    from core.tools.openshot import get_all_openshot_tools

    if isinstance(task_or_messages, str):
        messages = [{"role": "user", "content": task_or_messages}]
    else:
        messages = list(task_or_messages)

    # Transitions tools + all openshot tools (for listing clips, etc.)
    tools = list(get_transitions_tools()) + list(get_all_openshot_tools())
    # Deduplicate by name (transitions_tools are already in get_all_openshot_tools)
    seen = set()
    deduped = []
    for t in tools:
        name = getattr(t, "name", str(t))
        if name not in seen:
            seen.add(name)
            deduped.append(t)

    return run_agent_with_tools(
        model_id=model_id,
        messages=messages,
        tools=deduped,
        tool_executor=tool_executor,
        system_prompt=TRANSITIONS_SYSTEM_PROMPT,
    )


def run_research_agent(model_id, task_or_messages, tool_executor=None):
    """Run the Research agent (Perplexity) with research + openshot tools."""
    from core.chat.agent_runner import run_agent_with_tools
    from core.tools.research_tools import get_research_tools_for_langchain
    from core.tools.openshot import get_all_openshot_tools

    if isinstance(task_or_messages, str):
        messages = [{"role": "user", "content": task_or_messages}]
    else:
        messages = list(task_or_messages)

    tools = list(get_research_tools_for_langchain()) + list(get_all_openshot_tools())
    return run_agent_with_tools(
        model_id=model_id,
        messages=messages,
        tools=tools,
        tool_executor=tool_executor,
        system_prompt=RESEARCH_SYSTEM_PROMPT,
    )


def run_product_launch_agent(model_id, task_or_messages, tool_executor=None):
    """Run the Product Launch agent with GitHub + Manim tools."""
    from core.chat.agent_runner import run_agent_with_tools
    try:
        from core.tools.product_launch_tools import get_product_launch_tools_for_langchain
    except ImportError as e:
        log.debug("Product launch tools not available: %s", e)
        return "Product launch agent is not available."

    if isinstance(task_or_messages, str):
        messages = [{"role": "user", "content": task_or_messages}]
    else:
        messages = list(task_or_messages)

    tools = get_product_launch_tools_for_langchain()
    return run_agent_with_tools(
        model_id=model_id,
        messages=messages,
        tools=tools,
        tool_executor=tool_executor,
        system_prompt=PRODUCT_LAUNCH_SYSTEM_PROMPT,
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
