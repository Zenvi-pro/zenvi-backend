"""
Manim tools — generate educational/math animation videos.
Ported from zenvi-core; rendering runs server-side.
"""

from logger import log


def generate_manim_video(description: str, model_id: str = "") -> str:
    """Generate a Manim video from a natural-language description."""
    try:
        import subprocess
        import tempfile
        import os

        from core.llm import get_model, get_default_model_id

        mid = model_id or get_default_model_id()
        llm = get_model(mid)
        if not llm:
            return "Error: Could not load LLM for Manim code generation."

        # Ask LLM to generate Manim code
        from langchain_core.messages import HumanMessage, SystemMessage
        messages = [
            SystemMessage(content=(
                "You are a Manim expert. Generate a complete, runnable Manim Community Edition Python script. "
                "The script must define a Scene subclass. Output ONLY the Python code, no markdown."
            )),
            HumanMessage(content=f"Create a Manim animation: {description}"),
        ]
        response = llm.invoke(messages)
        code = response.content if hasattr(response, "content") else str(response)

        # Clean code
        if "```python" in code:
            code = code.split("```python", 1)[1].split("```", 1)[0]
        elif "```" in code:
            code = code.split("```", 1)[1].split("```", 1)[0]

        # Write and render
        work_dir = tempfile.mkdtemp(prefix="zenvi_manim_")
        script_path = os.path.join(work_dir, "scene.py")
        with open(script_path, "w") as f:
            f.write(code)

        result = subprocess.run(
            ["manim", "render", "-ql", script_path],
            capture_output=True, text=True, timeout=120, cwd=work_dir,
        )

        if result.returncode != 0:
            return f"Manim render failed: {result.stderr[:500]}"

        # Find output
        media_dir = os.path.join(work_dir, "media", "videos")
        for root, dirs, files in os.walk(media_dir):
            for f in files:
                if f.endswith(".mp4"):
                    return f"Manim video generated: {os.path.join(root, f)}"

        return "Manim render completed but no output video found."
    except Exception as e:
        log.error("Manim generation failed: %s", e)
        return f"Error: {e}"


def get_manim_tools_for_langchain():
    from langchain_core.tools import tool

    @tool
    def generate_manim_video_tool(description: str) -> str:
        """Generate a Manim educational/math animation video from a description."""
        return generate_manim_video(description)

    return [generate_manim_video_tool]
