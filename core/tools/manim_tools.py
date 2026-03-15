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

        import sys
        result = subprocess.run(
            [sys.executable, "-m", "manim", "render", "-ql", script_path],
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


def _get_manim_scenes(script_path: str) -> list:
    """Parse a Manim script to find Scene subclass names."""
    import re
    scenes = []
    try:
        with open(script_path, "r", encoding="utf-8") as f:
            code = f.read()
        # Match class Foo(Scene): or class Foo(MovingCameraScene): etc.
        for m in re.finditer(r"class\s+(\w+)\s*\([^)]*Scene[^)]*\)", code):
            scenes.append(m.group(1))
    except Exception as e:
        log.error("Failed to parse manim script: %s", e)
    return scenes


def _render_manim_scene(script_path: str, scene_name: str, quality: str = "l", output_dir: str = "") -> tuple:
    """Render a single Manim scene. Returns (video_path, error_string)."""
    import subprocess
    import os

    import sys
    quality_flag = f"-q{quality}" if quality else "-ql"
    cmd = [sys.executable, "-m", "manim", "render", quality_flag, script_path, scene_name]
    if output_dir:
        cmd.extend(["--media_dir", output_dir])
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            return None, result.stderr[:500]
        # Find the output video
        search_dir = output_dir or os.path.join(os.path.dirname(script_path), "media")
        for root, _dirs, files in os.walk(search_dir):
            for f in files:
                if f.endswith(".mp4") and scene_name.lower() in root.lower():
                    return os.path.join(root, f), None
        # Fallback: any mp4
        for root, _dirs, files in os.walk(search_dir):
            for f in files:
                if f.endswith(".mp4"):
                    return os.path.join(root, f), None
        return None, "No output video found."
    except subprocess.TimeoutExpired:
        return None, "Manim render timed out."
    except Exception as e:
        return None, str(e)


def _concatenate_videos_ffmpeg(video_paths: list, output_path: str) -> tuple:
    """Concatenate videos using ffmpeg. Returns (success, error_string)."""
    import subprocess
    import tempfile
    import os

    if len(video_paths) == 1:
        import shutil
        shutil.copy2(video_paths[0], output_path)
        return True, None

    list_file = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
    try:
        for vp in video_paths:
            list_file.write(f"file '{vp}'\n")
        list_file.close()

        cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_file.name, "-c", "copy", output_path]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            return False, result.stderr[:500]
        return True, None
    except Exception as e:
        return False, str(e)
    finally:
        try:
            os.unlink(list_file.name)
        except Exception:
            pass


def get_manim_tools_for_langchain():
    from langchain_core.tools import tool

    @tool
    def generate_manim_video_tool(description: str) -> str:
        """Generate a Manim educational/math animation video from a description."""
        return generate_manim_video(description)

    return [generate_manim_video_tool]
