"""
Root/supervisor agent — routes user requests to specialist sub-agents.
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
            """Route to the video/timeline agent. Use for: list files, add clips, export, timeline editing, generate video, split clips, and AI object replacement.
            IMPORTANT: Pass the user's message VERBATIM as the task, including any [Selected timeline clip context] blocks. Do NOT rephrase or summarize — the video agent needs the exact wording and context."""
            return sub_agents.run_video_agent(mid, task, te)

        @tool
        def invoke_manim_agent(task: str) -> str:
            """Route to the Manim agent for educational/math animation videos."""
            return sub_agents.run_manim_agent(mid, task, te)

        @tool
        def invoke_voice_music_agent(task: str) -> str:
            """Route to the voice/music agent for narration and music."""
            return sub_agents.run_voice_music_agent(mid, task, te)

        @tool
        def invoke_music_agent(task: str) -> str:
            """Route to the music agent for Suno background music generation and timeline insertion."""
            return sub_agents.run_music_agent(mid, task, te)

        @tool
        def invoke_transitions_agent(task: str) -> str:
            """Route to the transitions agent for adding professional transitions and effects. Has 412+ transitions: fades, wipes, circles, ripples, blurs, artistic effects."""
            return sub_agents.run_transitions_agent(mid, task, te)

        @tool
        def invoke_research_agent(task: str) -> str:
            """Route to the research agent for web search, content discovery, and theme planning. Use when user wants to research a topic, find images, apply a theme/style, or plan video aesthetics."""
            return sub_agents.run_research_agent(mid, task, te)

        @tool
        def invoke_product_launch_agent(task: str) -> str:
            """Route to the product launch agent for creating animated promotional videos from GitHub repositories. Use when user mentions product launch, launch video, or provides a GitHub URL."""
            return sub_agents.run_product_launch_agent(mid, task, te)

        @tool
        def invoke_remotion_agent(task: str) -> str:
            """Route to the Remotion rendering agent. Use when user mentions Remotion, remotion render, or wants to render a video using Remotion from a GitHub repository."""
            return sub_agents.run_remotion_agent(mid, task, te)

        @tool
        def invoke_directors(task: str) -> str:
            """Route to directors for video analysis, critique, and improvement planning. Use when user asks to analyze, critique, improve, or get feedback on their video."""
            from core.directors.director_orchestrator import run_directors
            from core.directors.director_loader import get_director_loader

            # Load all available directors by default
            loader = get_director_loader()
            available = loader.list_available_directors()
            if not available:
                return "No directors available. Add .director files to ~/.config/zenvi/directors/"
            director_ids = [d.id for d in available]

            return run_directors(
                model_id=mid,
                task=task,
                director_ids=director_ids,
                tool_executor=te,
            )

        @tool
        def spawn_parallel_versions(content_requests: list) -> str:
            """
            Spawn multiple parallel sub-agents for different content types.
            content_requests: list of dicts with title, content_type ("video"/"manim"/"voice_music"/"music"), instructions.
            Use ONLY when user explicitly requests multiple content types.
            """
            from core.agents.parallel_executor import run_sub_agents_parallel

            if not content_requests or not isinstance(content_requests, list):
                return "Error: content_requests must be a non-empty list."

            type_to_agent = {
                "video": "video", "manim": "manim",
                "voice_music": "voice_music", "music": "music",
                "transitions": "transitions", "research": "research",
                "product_launch": "product_launch",
            }
            calls = []
            for req in content_requests:
                title = req.get("title", "Untitled")
                ct = req.get("content_type", "video")
                instructions = req.get("instructions", "")
                agent_name = type_to_agent.get(ct, "video")
                calls.append((agent_name, mid, instructions, te))

            results = run_sub_agents_parallel(calls)

            parts = [f"Parallel execution of {len(results)} versions completed:"]
            for name, result in results:
                snippet = str(result)[:200]
                parts.append(f"- {name}: {snippet}")
            return "\n".join(parts)

        return [
            invoke_video_agent, invoke_manim_agent, invoke_voice_music_agent,
            invoke_music_agent, invoke_transitions_agent, invoke_research_agent,
            invoke_product_launch_agent, invoke_remotion_agent, invoke_directors,
            spawn_parallel_versions,
        ]

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
