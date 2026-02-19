"""
Tag manager — in-memory cache for AI-generated tags.
Ported from zenvi-core.
"""

from typing import Dict, List, Any, Optional
from logger import log


class TagManager:
    """Manages AI-generated tags (objects, scenes, activities, mood) per file."""

    def __init__(self):
        self._tags: Dict[str, Dict[str, Any]] = {}  # file_id -> tag data

    def add_tags(self, file_id: str, tags: Dict[str, Any]):
        if file_id not in self._tags:
            self._tags[file_id] = {}
        self._tags[file_id].update(tags)

    def get_tags(self, file_id: str) -> Dict[str, Any]:
        return self._tags.get(file_id, {})

    def get_all_tags(self) -> Dict[str, Dict[str, Any]]:
        return dict(self._tags)

    def remove_tags(self, file_id: str):
        self._tags.pop(file_id, None)

    def search_by_tag(self, tag_value: str, tag_type: Optional[str] = None) -> List[str]:
        """Return file_ids matching a tag value."""
        results = []
        tag_lower = tag_value.lower()
        for file_id, tags in self._tags.items():
            if tag_type:
                values = tags.get(tag_type, [])
                if isinstance(values, list) and any(tag_lower in str(v).lower() for v in values):
                    results.append(file_id)
            else:
                for key, values in tags.items():
                    if isinstance(values, list) and any(tag_lower in str(v).lower() for v in values):
                        results.append(file_id)
                        break
        return results

    def get_statistics(self) -> Dict[str, Any]:
        total_files = len(self._tags)
        all_tags = set()
        for tags in self._tags.values():
            for key, values in tags.items():
                if isinstance(values, list):
                    all_tags.update(str(v) for v in values)
        return {"total_files": total_files, "total_tags": len(all_tags)}


_instance: Optional[TagManager] = None


def get_tag_manager() -> TagManager:
    global _instance
    if _instance is None:
        _instance = TagManager()
    return _instance
