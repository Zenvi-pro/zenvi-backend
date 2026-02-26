"""
Server-side product launch video tools.
Handles GitHub data fetch + Manim code generation + rendering.
Adding the resulting video to the timeline is handled by existing
frontend-delegated tools (add_clip_to_timeline_tool).
"""

from __future__ import annotations

import json
import os
import tempfile
from typing import Any, Dict

from logger import log


# Module-level cache: avoids sending huge JSON through the LLM round-trip.
_repo_data_cache: Dict[str, Any] = {}


def _get_github_token() -> str:
    from config import get_settings
    return (get_settings().github_token or "").strip()


def fetch_github_repo_data(repo_url: str) -> str:
    """Fetch GitHub repo metadata + README. Returns JSON summary; caches full data."""
    from core.providers.github_client import get_repo_data_from_url, GitHubError, parse_github_url

    try:
        owner, repo = parse_github_url(repo_url)
        if not owner or not repo:
            return json.dumps({"error": f"Could not parse GitHub URL: {repo_url}",
                               "detail": "Expected: github.com/owner/repo or owner/repo"})

        token = _get_github_token()
        log.info("Fetching GitHub data for %s/%s ...", owner, repo)
        data = get_repo_data_from_url(repo_url, token=token)

        repo_info = data.get("repo_info", {})
        result = {
            "success": True,
            "owner": data.get("owner"),
            "repo": data.get("repo"),
            "name": repo_info.get("name"),
            "description": repo_info.get("description"),
            "stars": repo_info.get("stargazers_count", 0),
            "forks": repo_info.get("forks_count", 0),
            "watchers": repo_info.get("watchers_count", 0),
            "language": repo_info.get("language"),
            "topics": repo_info.get("topics", []),
            "homepage": repo_info.get("homepage"),
            "readme_preview": (data.get("readme", "")[:500] + "...") if len(data.get("readme", "")) > 500 else data.get("readme", ""),
            "full_data": data,
        }

        cache_key = f"{owner}/{repo}"
        _repo_data_cache[cache_key] = result
        _repo_data_cache["_latest"] = result
        log.info("Cached repo data under '%s'", cache_key)

        summary = {
            "success": True, "owner": result["owner"], "repo": result["repo"],
            "name": result["name"], "description": result["description"],
            "stars": result["stars"], "forks": result["forks"],
            "language": result["language"], "topics": result["topics"],
            "cache_key": cache_key,
            "instruction": "Now call generate_product_launch_video with this JSON",
        }
        return json.dumps(summary)

    except Exception as e:
        log.error("GitHub fetch failed: %s", e, exc_info=True)
        return json.dumps({"error": str(e)})


def _resolve_cached_data(repo_data_json: str) -> Dict[str, Any] | None:
    """Parse JSON and/or fall back to the module cache."""
    data = None
    try:
        data = json.loads(repo_data_json, strict=False)
    except (json.JSONDecodeError, TypeError):
        pass

    cache_key = None
    if data:
        cache_key = data.get("cache_key") or (
            f"{data['owner']}/{data['repo']}" if "owner" in data and "repo" in data else None
        )
    cached = _repo_data_cache.get(cache_key) if cache_key else None
    if not cached:
        cached = _repo_data_cache.get("_latest")
    return cached or data


def generate_product_launch_video(repo_data_json: str) -> str:
    """
    Generate a product launch video via Manim.
    Returns the path to the combined MP4 so the caller can add it to the timeline.
    """
    data = _resolve_cached_data(repo_data_json)
    if not data:
        return "Error: Could not parse repo data. Call fetch_github_repo_data first."
    if "error" in data:
        return f"Error: {data['error']}"

    full_data = data.get("full_data")
    if not full_data:
        return "Error: full_data missing — call fetch_github_repo_data first."

    import shutil
    manim_available = shutil.which("manim") is not None
    if not manim_available:
        try:
            import manim as _test  # noqa: F401
            manim_available = True
        except ImportError:
            pass
    if not manim_available:
        return "Error: Manim is not installed. pip install manim"

    repo_name = f"{data.get('owner')}/{data.get('repo')}"
    log.info("Product launch video for %s — generating Manim code", repo_name)

    try:
        from core.tools.product_launch_tools import _generate_product_launch_manim_code
        manim_code = _generate_product_launch_manim_code(full_data)
    except Exception as e:
        log.error("Code generation failed: %s", e, exc_info=True)
        return f"Error generating Manim code: {e}"

    tmpdir = tempfile.mkdtemp(prefix="zenvi_product_launch_")
    script_path = os.path.join(tmpdir, "product_launch.py")
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(manim_code)

    try:
        from core.tools.manim_tools import _get_manim_scenes, _render_manim_scene, _concatenate_videos_ffmpeg
    except ImportError:
        return "Error: Manim tools not available on backend."

    scenes = _get_manim_scenes(script_path)
    if not scenes:
        return "Error: No Scene classes found in generated code."

    output_dir = os.path.join(tmpdir, "media")
    os.makedirs(output_dir, exist_ok=True)
    video_paths, errors = [], []

    for scene_name in scenes:
        log.info("Rendering scene %s ...", scene_name)
        path, err = _render_manim_scene(script_path, scene_name, quality="l", output_dir=output_dir)
        if err:
            errors.append(f"{scene_name}: {err}")
        elif path:
            video_paths.append(path)

    if not video_paths:
        return "Error: All scenes failed to render:\n" + "\n".join(errors)

    combined_path = os.path.join(tmpdir, "product_launch_combined.mp4")
    ok, err = _concatenate_videos_ffmpeg(video_paths, combined_path)
    if not ok:
        return f"Error concatenating scenes: {err}"

    if not os.path.exists(combined_path):
        return f"Error: Video not created at {combined_path}"

    size_mb = os.path.getsize(combined_path) / (1024 * 1024)
    log.info("Product launch video ready: %s (%.2f MB)", combined_path, size_mb)
    return (
        f"Product launch video generated for '{data.get('name', repo_name)}'.\n"
        f"Path: {combined_path}\n"
        f"Scenes: {', '.join(scenes)}\n"
        f"Size: {size_mb:.2f} MB\n"
        "Use add_clip_to_timeline_tool to add this video to the timeline."
    )


# ---------------------------------------------------------------------------
# Manim code generator (ported from core/ai_product_launch_tools.py)
# ---------------------------------------------------------------------------

def _generate_product_launch_manim_code(repo_data: Dict[str, Any]) -> str:
    """Generate Manim code for a product launch video."""
    import re as _re

    repo_info = repo_data.get("repo_info", {})
    readme = repo_data.get("readme", "")
    owner = repo_data.get("owner", "")
    repo = repo_data.get("repo", "")

    name = repo_info.get("name", repo)
    description = repo_info.get("description", "")
    stars = repo_info.get("stargazers_count", 0)
    forks = repo_info.get("forks_count", 0)
    language = repo_info.get("language", "")
    homepage = repo_info.get("homepage", "")

    def fmt(n):
        if n >= 1_000_000:
            return f"{n / 1_000_000:.1f}M"
        if n >= 1000:
            return f"{n / 1000:.1f}K"
        return str(n)

    stars_str, forks_str = fmt(stars), fmt(forks)

    features = []
    if readme:
        for line in readme.split("\n")[:50]:
            s = line.strip()
            if s.startswith(("- ", "* ", "+ ")) and 5 < len(s) < 100:
                feat = s[2:].strip()
                if feat and not feat.lower().startswith(("http", "see ", "read ", "[", "!")):
                    features.append(feat)
                    if len(features) >= 3:
                        break

    if len(description) > 80:
        description = description[:77] + "..."

    def esc(s):
        if not s:
            return ""
        s = s.replace("\\", "\\\\").replace('"', '\\"').replace("'", "\\'")
        s = s.replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
        s = _re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", s)
        return s[:200]

    name_e = esc(name)
    desc_e = esc(description)
    owner_e = esc(owner)
    repo_e = esc(repo)
    feats_e = [esc(f) for f in features[:3]]

    code = f'''from manim import *

class IntroScene(Scene):
    def construct(self):
        title = Text("{name_e}", font_size=60, weight=BOLD).set_color(BLUE)
        desc = Text("{desc_e}", font_size=28).next_to(title, DOWN, buff=0.5).set_color(GRAY)
        gh = Text("github.com/{owner_e}/{repo_e}", font_size=22).next_to(desc, DOWN, buff=0.6).set_color(GREEN)
        self.play(FadeIn(title), run_time=0.5)
        self.play(FadeIn(desc), run_time=0.4)
        self.play(FadeIn(gh), run_time=0.3)
        self.wait(1)
        self.play(FadeOut(title), FadeOut(desc), FadeOut(gh), run_time=0.5)


class StatsScene(Scene):
    def construct(self):
        t = Text("Repository Stats", font_size=48, weight=BOLD).to_edge(UP, buff=0.8).set_color(YELLOW)
        star_g = VGroup(Text("⭐", font_size=48), Text("Stars", font_size=32),
                        Text("{stars_str}", font_size=48, weight=BOLD).set_color(YELLOW)).arrange(DOWN, buff=0.3).shift(LEFT * 3)
        fork_g = VGroup(Text("🔀", font_size=48), Text("Forks", font_size=32),
                        Text("{forks_str}", font_size=48, weight=BOLD).set_color(BLUE)).arrange(DOWN, buff=0.3)
'''
    if language:
        lang_e = esc(language)
        code += f'''        lang_g = VGroup(Text("💻", font_size=48), Text("Language", font_size=32),
                        Text("{lang_e}", font_size=36, weight=BOLD).set_color(GREEN)).arrange(DOWN, buff=0.3).shift(RIGHT * 3)
        all_s = VGroup(star_g, fork_g, lang_g)
'''
    else:
        code += "        all_s = VGroup(star_g, fork_g)\n"

    code += '''        self.play(FadeIn(t), run_time=0.4)
        self.play(LaggedStart(*[FadeIn(g, shift=UP) for g in all_s], lag_ratio=0.2), run_time=1)
        self.wait(1)
        self.play(FadeOut(t), FadeOut(all_s), run_time=0.5)
'''

    if feats_e:
        feat_lines = "\n".join(f'        f{i+1} = Text("• {f}", font_size=28)' for i, f in enumerate(feats_e))
        feat_names = ", ".join(f"f{i+1}" for i in range(len(feats_e)))
        code += f'''

class FeaturesScene(Scene):
    def construct(self):
        t = Text("Key Features", font_size=48, weight=BOLD).to_edge(UP, buff=0.8).set_color(TEAL)
        self.play(FadeIn(t), run_time=0.4)
{feat_lines}
        fg = VGroup({feat_names}).arrange(DOWN, aligned_edge=LEFT, buff=0.4).next_to(t, DOWN, buff=0.8)
        self.play(FadeIn(fg, shift=RIGHT), run_time=0.8)
        self.wait(1)
        self.play(FadeOut(t), FadeOut(fg), run_time=0.5)
'''

    code += f'''

class OutroScene(Scene):
    def construct(self):
        cta = Text("Check it out!", font_size=64, weight=BOLD).set_color_by_gradient(BLUE, GREEN)
        url = Text("github.com/{owner_e}/{repo_e}", font_size=36).next_to(cta, DOWN, buff=0.8).set_color(WHITE)
'''
    if homepage:
        hp_e = esc(homepage)
        code += f'        hp = Text("{hp_e}", font_size=28).next_to(url, DOWN, buff=0.5).set_color(GRAY)\n'

    code += "        self.play(FadeIn(cta), run_time=0.5)\n        self.play(FadeIn(url), run_time=0.4)\n"
    if homepage:
        code += "        self.play(FadeIn(hp), run_time=0.3)\n"
    code += "        self.wait(1)\n"
    outs = "FadeOut(cta), FadeOut(url)"
    if homepage:
        outs += ", FadeOut(hp)"
    code += f"        self.play({outs}, run_time=0.5)\n"

    return code


# ---------------------------------------------------------------------------
# LangChain tools
# ---------------------------------------------------------------------------

def get_product_launch_tools_for_langchain():
    from langchain_core.tools import tool

    @tool
    def fetch_github_repo_data_tool(repo_url: str) -> str:
        """
        Fetch GitHub repository data. After this, IMMEDIATELY call generate_product_launch_video_tool with the result.

        Args:
            repo_url: GitHub URL (github.com/owner/repo or owner/repo)
        """
        return fetch_github_repo_data(repo_url)

    @tool
    def generate_product_launch_video_tool(repo_data_json: str) -> str:
        """
        Generate a product launch video using Manim animations from GitHub repo data.
        Pass the JSON string from fetch_github_repo_data_tool.
        The video is saved locally; use add_clip_to_timeline_tool to add it to the project.
        """
        return generate_product_launch_video(repo_data_json)

    return [fetch_github_repo_data_tool, generate_product_launch_video_tool]
