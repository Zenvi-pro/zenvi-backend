"""
Google provider — Gemma 3 27B for media analysis via the Gemini API.

Video analysis pipeline:
  1. Extract one JPEG frame every 2 seconds (up to MAX_FRAMES) with cv2.
  2. Upload each frame to the Files API (client.files.upload).
  3. Submit all file references + a structured prompt to gemma-3-27b-it.
  4. Parse the JSON response into an AnalysisResult.
  5. Delete uploaded files and temp JPEGs.

Single-image analysis follows the same Files API path (no frame extraction).
"""

import os
import json
import mimetypes
import tempfile
from typing import Optional, List, Dict, Any, Tuple

from logger import log
from core.providers import BaseAIProvider, AnalysisResult, ProviderType, ProviderFactory

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GEMMA_MODEL = "gemma-3-27b-it"
MAX_FRAMES = 20                 # max frames uploaded per request
FRAME_INTERVAL_SEC = 2.0        # sample one frame every N seconds

VIDEO_EXTENSIONS = {
    ".mp4", ".mov", ".avi", ".mkv", ".webm",
    ".m4v", ".flv", ".wmv", ".ts", ".mts",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_video(path: str) -> bool:
    ext = os.path.splitext(path)[1].lower()
    if ext in VIDEO_EXTENSIONS:
        return True
    mime, _ = mimetypes.guess_type(path)
    return bool(mime and mime.startswith("video/"))


def _strip_markdown_fences(text: str) -> str:
    """Remove ```json ... ``` or ``` ... ``` wrappers from a model response."""
    text = text.strip()
    if text.startswith("```"):
        first_newline = text.find("\n")
        text = text[first_newline + 1:] if first_newline != -1 else text[3:]
    if text.endswith("```"):
        text = text[: text.rfind("```")]
    return text.strip()


# ---------------------------------------------------------------------------
# Provider class
# ---------------------------------------------------------------------------

class GeminiProvider(BaseAIProvider):
    """
    Gemma 3 27B vision provider.
    Uses the Gemini Developer API with the Files API for frame uploads.
    """

    def __init__(self, api_key: Optional[str] = None, **kwargs):
        self.model_name = kwargs.get("model", GEMMA_MODEL)
        super().__init__(api_key, **kwargs)

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def _validate_configuration(self) -> bool:
        if not self.api_key or len(self.api_key) < 10:
            log.warning("Google API key not configured for Gemma provider")
            self.is_configured = False
            return False
        self.is_configured = True
        return True

    # ------------------------------------------------------------------
    # Frame extraction
    # ------------------------------------------------------------------

    def _extract_frames(
        self, video_path: str, max_frames: int = MAX_FRAMES
    ) -> List[Tuple[float, str]]:
        """
        Extract one JPEG frame every FRAME_INTERVAL_SEC from *video_path*.

        Returns a list of (timestamp_seconds, tmp_jpeg_path) tuples.
        The caller owns the temp files and must delete them.
        """
        try:
            import cv2  # type: ignore
        except ImportError:
            log.error("opencv-python not installed — cannot extract video frames")
            return []

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            log.error("Cannot open video: %s", video_path)
            return []

        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = frame_count / fps if fps > 0 else 0.0

        frames: List[Tuple[float, str]] = []
        t = 0.0
        while t <= duration and len(frames) < max_frames:
            frame_idx = int(t * fps)
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ok, frame = cap.read()
            if not ok:
                break

            tmp = tempfile.NamedTemporaryFile(
                suffix=".jpg",
                prefix=f"frame_{int(t):04d}_",
                delete=False,
            )
            tmp.close()
            cv2.imwrite(tmp.name, frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            frames.append((t, tmp.name))
            t += FRAME_INTERVAL_SEC

        cap.release()
        log.debug(
            "Extracted %d frames from %s (fps=%.1f, duration=%.1fs)",
            len(frames), video_path, fps, duration,
        )
        return frames

    # ------------------------------------------------------------------
    # Files API helpers
    # ------------------------------------------------------------------

    def _upload_files_sync(self, client, paths: List[str]):
        """
        Upload a list of JPEG paths via the Files API.
        Returns a list of file objects (each has .name and .uri).
        """
        from google.genai import types as gt  # type: ignore

        uploaded = []
        for path in paths:
            try:
                f = client.files.upload(
                    file=path,
                    config=gt.UploadFileConfig(mime_type="image/jpeg"),
                )
                uploaded.append(f)
            except Exception as exc:
                log.warning("Frame upload failed for %s: %s", path, exc)
        return uploaded

    def _delete_files_sync(self, client, uploaded_files: list) -> None:
        """Delete files from the Files API (best-effort)."""
        for f in uploaded_files:
            try:
                client.files.delete(name=f.name)
            except Exception as exc:
                log.debug(
                    "Could not delete uploaded file %s: %s",
                    getattr(f, "name", "?"), exc,
                )

    # ------------------------------------------------------------------
    # Structured prompts
    # ------------------------------------------------------------------

    _ANALYSIS_FIELDS = (
        "objects: list of visible objects/subjects\n"
        "scenes: list of scene/location descriptors\n"
        "activities: list of actions or events happening\n"
        "mood: list of mood/atmosphere descriptors\n"
        "colors: {dominant: list, palette: list}\n"
        "faces: list of {age_range, gender, expression, confidence}\n"
        "description: one-sentence natural-language summary\n"
        "confidence: float 0-1\n"
        "quality_scores: {overall: float, sharpness: float, brightness: float}\n"
        "scene_descriptions: list of {time: int, description: str} — one entry per frame\n"
        "Return ONLY valid JSON, no markdown fences."
    )

    def _make_video_prompt(self, n_frames: int, timestamps: List[float]) -> str:
        ts_str = ", ".join(f"{int(t)}s" for t in timestamps[:n_frames])
        return (
            f"The following {n_frames} images are frames extracted every 2 seconds from a video "
            f"(timestamps: {ts_str}). Analyse the complete video and return ONLY a valid JSON "
            "object with these fields:\n" + self._ANALYSIS_FIELDS
        )

    def _make_image_prompt(self) -> str:
        return (
            "Analyse this image and return ONLY a valid JSON object with these fields:\n"
            + self._ANALYSIS_FIELDS
        )

    # ------------------------------------------------------------------
    # Response parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _apply_timestamps(
        result: AnalysisResult, timestamps: List[float]
    ) -> AnalysisResult:
        """
        Overwrite scene_descriptions[i]["time_seconds"] with the actual
        timestamp for frame i.  The model often returns 0 for every entry
        because it has no intrinsic sense of playback time.
        """
        scene_descs = result.raw_response.get("scene_descriptions", [])
        for i, entry in enumerate(scene_descs):
            if i < len(timestamps):
                entry["time"] = int(timestamps[i])
            elif scene_descs:  # pad remaining entries beyond known timestamps
                entry["time"] = int(i * FRAME_INTERVAL_SEC)
        return result

    @staticmethod
    def _parse_response(raw: str, provider_tag: str = "gemma-3-27b") -> AnalysisResult:
        raw = _strip_markdown_fences(raw)
        data = json.loads(raw)

        result = AnalysisResult()
        result.provider = provider_tag
        result.objects = data.get("objects", [])
        result.scenes = data.get("scenes", [])
        result.activities = data.get("activities", [])
        result.mood = data.get("mood", [])
        result.colors = data.get("colors", {})
        result.faces = data.get("faces", [])
        result.description = data.get("description", "")
        result.confidence = float(data.get("confidence", 0.8))
        result.quality_scores = data.get("quality_scores", {})
        result.raw_response = {
            "scene_descriptions": [
                {"time": s.get("time", s.get("time_seconds", 0)), "description": s.get("description", "")}
                for s in data.get("scene_descriptions", [])
            ]
        }
        return result

    # ------------------------------------------------------------------
    # Core synchronous analysis (runs inside run_in_executor)
    # ------------------------------------------------------------------

    def _analyse_sync(self, path: str) -> AnalysisResult:
        """
        Synchronous implementation of the full analysis pipeline.
        Blocks — callers must run it in a thread executor.
        """
        from google import genai  # type: ignore
        from google.genai import types as gt  # type: ignore

        empty = AnalysisResult()
        empty.provider = "gemma-3-27b"

        client = genai.Client(api_key=self.api_key)
        tmp_paths: List[str] = []
        uploaded_files = []
        raw = ""

        try:
            if _is_video(path):
                # ── Video: extract frames every 2 seconds ──────────────
                frame_tuples = self._extract_frames(path, max_frames=MAX_FRAMES)
                if not frame_tuples:
                    log.warning("No frames extracted from %s", path)
                    return empty

                timestamps = [t for t, _ in frame_tuples]
                tmp_paths = [p for _, p in frame_tuples]

                uploaded_files = self._upload_files_sync(client, tmp_paths)
                if not uploaded_files:
                    log.warning("All frame uploads failed for %s", path)
                    return empty

                prompt = self._make_video_prompt(len(uploaded_files), timestamps)
                contents = list(uploaded_files) + [prompt]

            else:
                # ── Single image ────────────────────────────────────────
                mime, _ = mimetypes.guess_type(path)
                mime = mime or "image/jpeg"
                f = client.files.upload(
                    file=path,
                    config=gt.UploadFileConfig(mime_type=mime),
                )
                uploaded_files = [f]
                contents = [f, self._make_image_prompt()]

            # ── Inference ──────────────────────────────────────────────
            response = client.models.generate_content(
                model=self.model_name,
                contents=contents,
                config=gt.GenerateContentConfig(
                    temperature=0.2,
                    max_output_tokens=2048,
                ),
            )

            raw = response.text or ""
            result = self._parse_response(raw)
            if _is_video(path):
                self._apply_timestamps(result, timestamps)
            return result

        except json.JSONDecodeError as exc:
            log.error(
                "Gemma JSON parse error: %s — raw snippet: %.300s",
                exc, raw,
            )
            return empty
        except Exception as exc:
            log.error("Gemma analysis failed for %s: %s", path, exc, exc_info=True)
            return empty
        finally:
            # Always clean up: Files API uploads and local temp JPEGs
            if uploaded_files:
                self._delete_files_sync(client, uploaded_files)
            for p in tmp_paths:
                try:
                    os.unlink(p)
                except OSError:
                    pass

    # ------------------------------------------------------------------
    # Abstract method implementations
    # ------------------------------------------------------------------

    async def analyze_image(self, image_path: str, **kwargs) -> AnalysisResult:
        """
        Analyse an image or video file.

        For videos, frames are extracted every 2 seconds, uploaded via the
        Files API, and submitted together to Gemma 3 27B for a single
        comprehensive inference pass.
        """
        if not self.is_available():
            empty = AnalysisResult()
            empty.provider = "gemma-3-27b"
            return empty

        import asyncio
        try:
            return await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._analyse_sync(image_path)
            )
        except Exception as exc:
            log.error("analyze_image async wrapper failed: %s", exc, exc_info=True)
            empty = AnalysisResult()
            empty.provider = "gemma-3-27b"
            return empty

    async def analyze_video_frames(
        self, frame_paths: List[str], **kwargs
    ) -> AnalysisResult:
        """
        Analyse a list of pre-extracted frame paths.

        If a single video file path is passed, delegates to analyze_image
        (which performs frame extraction internally). Otherwise the frame
        paths are uploaded directly to the Files API as a batch.
        """
        empty = AnalysisResult()
        empty.provider = "gemma-3-27b"

        if not frame_paths or not self.is_available():
            return empty

        # Single video file → let analyze_image handle frame extraction
        if len(frame_paths) == 1 and _is_video(frame_paths[0]):
            return await self.analyze_image(frame_paths[0], **kwargs)

        # Pre-extracted frames: batch-upload them directly
        def _sync_batch() -> AnalysisResult:
            from google import genai  # type: ignore
            from google.genai import types as gt  # type: ignore

            client = genai.Client(api_key=self.api_key)
            batch = frame_paths[:MAX_FRAMES]
            uploaded_files = self._upload_files_sync(client, batch)
            if not uploaded_files:
                return empty

            raw = ""
            try:
                timestamps: List[float] = [
                    i * FRAME_INTERVAL_SEC for i in range(len(uploaded_files))
                ]
                prompt = self._make_video_prompt(len(uploaded_files), timestamps)
                response = client.models.generate_content(
                    model=self.model_name,
                    contents=list(uploaded_files) + [prompt],
                    config=gt.GenerateContentConfig(
                        temperature=0.2,
                        max_output_tokens=2048,
                    ),
                )
                raw = response.text or ""
                result = self._parse_response(raw)
                self._apply_timestamps(result, timestamps)
                return result
            except Exception as exc:
                log.error(
                    "analyze_video_frames batch call failed: %s", exc, exc_info=True
                )
                return empty
            finally:
                self._delete_files_sync(client, uploaded_files)

        import asyncio
        return await asyncio.get_event_loop().run_in_executor(None, _sync_batch)

    async def detect_faces(self, image_path: str) -> List[Dict[str, Any]]:
        """Detect faces via Gemma 3 27B (piggybacks on analyze_image)."""
        result = await self.analyze_image(image_path)
        return result.faces

    async def parse_search_query(self, query: str) -> Dict[str, Any]:
        """Not implemented for this provider."""
        return {}


# Register with the factory
ProviderFactory.register_provider(ProviderType.GOOGLE, GeminiProvider)
