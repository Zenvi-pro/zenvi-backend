"""
Root/supervisor agent — routes user requests to Video, Manim, or Voice/Music sub-agents.
Ported from zenvi-core; no Qt dependency.
"""

from core.chat.prompts import ROOT_SYSTEM_PROMPT


def run_root_agent(model_id, messages, tool_executor=None, timeout_seconds=120):
    """
    Run the root agent with invoke_* routing tools.
    tool_executor: callback for delegating frontend tool calls.
    """
    from core.chat.agent_runner import run_agent_with_tools

    def make_invoke_tools():
        from langchain_core.tools import tool
        from core.agents import sub_agents
        mid = model_id
        te = tool_executor

        @tool
        def invoke_video_agent(task: str) -> str:
            """Route to the video/timeline agent."""
            return sub_agents.run_video_agent(mid, task, te)

        @tool
        def invoke_manim_agent(task: str) -> str:
            """Route to the Manim agent for educational/math animation videos."""
            return sub_agents.run_manim_agent(mid, task, te)

        @tool
        def invoke_voice_music_agent(task: str) -> str:
            """Route to the voice/music agent for narration and music."""
            return sub_agents.run_voice_music_agent(mid, task, te)

        return [invoke_video_agent, invoke_manim_agent, invoke_voice_music_agent]

    root_tools = make_invoke_tools()
    return run_agent_with_tools(
        model_id=model_id,
        messages=messages,
        tools=root_tools,
        tool_executor=None,  # root tools run locally
        system_prompt=ROOT_SYSTEM_PROMPT,
        max_iterations=10,
        timeout_seconds=timeout_seconds,
    )
