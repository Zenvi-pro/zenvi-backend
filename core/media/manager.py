"""
AI media manager — orchestrates analysis, search, tagging, faces, collections.
Ported from zenvi-core; no Qt dependency.
"""

import asyncio
from typing import Dict, Any, Optional
from logger import log


class AIMediaManager:
    """Singleton orchestrator for AI media management."""

    def __init__(self):
        self._initialized = False

    async def process_command(self, command: str) -> Dict[str, Any]:
        """Process a natural-language media management command."""
        lower = command.lower()

        if "statistics" in lower or "stats" in lower:
            return await self._get_statistics()
        if "search" in lower or "find" in lower:
            query = command  # simplified
            return await self._search(query)
        if "analyze" in lower:
            return {"success": True, "action": "analyze", "message": "Analysis queued. Use the /media/analyze endpoint to submit files."}
        if "collection" in lower:
            return {"success": True, "action": "collection", "message": "Use the /collections endpoints for collection management."}
        if "tag" in lower:
            return {"success": True, "action": "tag", "message": "Use the /tags endpoints for tag management."}

        return {"success": False, "message": f"Unrecognized media command: {command}"}

    async def _search(self, query: str) -> Dict[str, Any]:
        try:
            from core.indexing.twelvelabs import search_index
            results = search_index(query)
            if isinstance(results, dict) and "error" in results:
                return {"success": False, "message": results["error"]}
            if not isinstance(results, list):
                results = []
            return {"success": True, "action": "search", "results": results, "message": f"Found {len(results)} results."}
        except Exception as e:
            return {"success": False, "message": f"Search failed: {e}"}

    async def _get_statistics(self) -> Dict[str, Any]:
        stats = {}
        try:
            from core.managers.tags import get_tag_manager
            stats["tags"] = get_tag_manager().get_statistics()
        except Exception:
            pass
        try:
            from core.managers.faces import get_face_manager
            stats["faces"] = get_face_manager().get_statistics()
        except Exception:
            pass
        try:
            from core.managers.collections import get_collection_manager
            stats["collections"] = get_collection_manager().get_statistics()
        except Exception:
            pass
        return {"success": True, "action": "statistics", "stats": stats, "message": "Statistics retrieved."}


_instance: Optional[AIMediaManager] = None


def get_ai_media_manager() -> AIMediaManager:
    global _instance
    if _instance is None:
        _instance = AIMediaManager()
    return _instance
