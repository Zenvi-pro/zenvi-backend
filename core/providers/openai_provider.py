"""
OpenAI provider — LangChain ChatOpenAI for chat and GPT-4 Vision for media analysis.
Ported from zenvi-core; no Qt or classes.app dependency.
"""

import os
import asyncio
import base64
import json
from typing import Dict, List, Any, Optional

from logger import log
from core.providers import BaseAIProvider, AnalysisResult, ProviderType, ProviderFactory


def _get_api_key(settings):
    """Get OpenAI API key from settings or environment."""
    key = ""
    if settings:
        key = (settings.get("openai-api-key") or "").strip()
    if not key:
        key = (os.environ.get("OPENAI_API_KEY") or os.environ.get("OPEN_AI_API_KEY") or "").strip()
    return key


def is_available(model_id, settings):
    if not model_id.startswith("openai/"):
        return False
    return bool(_get_api_key(settings))


def build_chat_model(model_id, settings):
    """Build ChatOpenAI for the given model_id."""
    try:
        from langchain_openai import ChatOpenAI
    except ImportError:
        log.warning("langchain-openai not installed")
        return None

    api_key = _get_api_key(settings)
    if not api_key:
        log.warning("No OpenAI API key found")
        return None

    model_name = model_id.split("/", 1)[-1] if "/" in model_id else model_id
    return ChatOpenAI(model=model_name, api_key=api_key, temperature=0.2, request_timeout=60)


class OpenAIProvider(BaseAIProvider):
    """OpenAI GPT-4 Vision provider for media analysis."""

    def __init__(self, api_key: Optional[str] = None, **kwargs):
        self.model = kwargs.get("model", "gpt-4-vision-preview")
        self.max_tokens = kwargs.get("max_tokens", 1000)
        self.temperature = kwargs.get("temperature", 0.7)
        super().__init__(api_key, **kwargs)

    def _validate_configuration(self) -> bool:
        if not self.api_key or len(self.api_key) < 10:
            log.warning("OpenAI API key not configured")
            self.is_configured = False
            return False
        self.is_configured = True
        return True

    def _encode_image(self, image_path: str) -> str:
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    async def _call_api(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        try:
            from openai import AsyncOpenAI
        except ImportError:
            log.error("openai package not installed")
            return {}
        client = AsyncOpenAI(api_key=self.api_key)
        try:
            response = await client.chat.completions.create(
                model=self.model, messages=messages, max_tokens=self.max_tokens, temperature=self.temperature
            )
            return {"content": response.choices[0].message.content, "usage": dict(response.usage) if response.usage else {}}
        except Exception as e:
            log.error("OpenAI API call failed: %s", e)
            return {}

    async def analyze_image(self, image_path: str, **kwargs) -> AnalysisResult:
        result = AnalysisResult()
        result.provider = "openai"
        try:
            b64 = self._encode_image(image_path)
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Analyze this image. Return JSON: {\"objects\":[], \"scenes\":[], \"activities\":[], \"mood\":[], \"description\":\"\", \"colors\":{\"dominant\":[], \"palette\":[]}, \"quality\":{\"lighting\":0-10, \"composition\":0-10, \"clarity\":0-10}}"},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                    ],
                }
            ]
            resp = await self._call_api(messages)
            content = resp.get("content", "")
            if content:
                data = json.loads(content) if isinstance(content, str) else content
                result.objects = data.get("objects", [])
                result.scenes = data.get("scenes", [])
                result.activities = data.get("activities", [])
                result.mood = data.get("mood", [])
                result.description = data.get("description", "")
                result.colors = data.get("colors", {})
                result.quality_scores = data.get("quality", {})
                result.confidence = 0.85
        except Exception as e:
            log.error("OpenAI image analysis failed: %s", e)
        return result

    async def analyze_video_frames(self, frame_paths: List[str], **kwargs) -> AnalysisResult:
        result = AnalysisResult()
        result.provider = "openai"
        all_objects, all_scenes, all_activities = set(), set(), set()
        for fp in frame_paths[:5]:
            r = await self.analyze_image(fp)
            all_objects.update(r.objects)
            all_scenes.update(r.scenes)
            all_activities.update(r.activities)
        result.objects = list(all_objects)
        result.scenes = list(all_scenes)
        result.activities = list(all_activities)
        result.confidence = 0.80
        return result

    async def detect_faces(self, image_path: str) -> List[Dict[str, Any]]:
        b64 = self._encode_image(image_path)
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Detect faces. Return JSON array: [{\"bbox\":{\"x\":,\"y\":,\"w\":,\"h\":}, \"confidence\":0-1, \"emotions\":{}, \"age_range\":\"\", \"gender\":\"\"}]"},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                ],
            }
        ]
        resp = await self._call_api(messages)
        content = resp.get("content", "")
        try:
            return json.loads(content) if isinstance(content, str) else content
        except Exception:
            return []

    async def parse_search_query(self, query: str) -> Dict[str, Any]:
        messages = [
            {"role": "system", "content": "Parse a media search query into structured filters. Return JSON: {\"objects\":[], \"scenes\":[], \"activities\":[], \"mood\":[], \"colors\":[], \"quality_min\":{}, \"time_range\":{}, \"text_query\":\"\"}"},
            {"role": "user", "content": query},
        ]
        resp = await self._call_api(messages)
        content = resp.get("content", "")
        try:
            return json.loads(content) if isinstance(content, str) else content
        except Exception:
            return {"text_query": query}


# Auto-register
ProviderFactory.register_provider(ProviderType.OPENAI, OpenAIProvider)
