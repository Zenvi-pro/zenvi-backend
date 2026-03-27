"""
Thread pool for running sub-agents in parallel.
Ported from zenvi-core.
"""

import concurrent.futures
from logger import log

_executor = concurrent.futures.ThreadPoolExecutor(max_workers=4, thread_name_prefix="zenvi_subagent")


def submit_sub_agent(agent_name, model_id, messages, tool_executor=None):
    from core.agents import sub_agents
    runners = {
        "video": sub_agents.run_video_agent,
        "manim": sub_agents.run_manim_agent,
        "voice_music": sub_agents.run_voice_music_agent,
        "transitions": sub_agents.run_transitions_agent,
        "research": sub_agents.run_research_agent,
        "product_launch": sub_agents.run_product_launch_agent,
    }
    fn = runners.get(agent_name)
    if not fn:
        return _executor.submit(lambda: f"Error: unknown agent {agent_name}")
    return _executor.submit(fn, model_id, messages, tool_executor)


def run_sub_agents_parallel(calls):
    """
    calls: list of (agent_name, model_id, messages, tool_executor).
    Returns list of (agent_name, result_string).
    """
    futures = []
    names = []
    for agent_name, model_id, messages, te in calls:
        futures.append(submit_sub_agent(agent_name, model_id, messages, te))
        names.append(agent_name)
    results = []
    for name, fut in zip(names, futures):
        try:
            results.append((name, fut.result(timeout=120)))
        except Exception as e:
            log.error("Sub-agent %s failed: %s", name, e, exc_info=True)
            results.append((name, f"Error: {e}"))
    return results
