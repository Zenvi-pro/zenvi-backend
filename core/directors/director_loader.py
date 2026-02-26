"""
Director Loader — loads and validates .director JSON files.

Ported from core/src/classes/ai_directors/director_loader.py.
Uses a configurable directors path instead of ``classes.info.PATH``.
"""

import json
import os
from typing import List, Optional

from logger import log
from core.directors.director_agent import (
    Director,
    DirectorMetadata,
    DirectorPersonality,
    DirectorTraining,
)


def _default_builtin_dir() -> str:
    """Return default built-in directors directory.

    Looks for a ``directors/built_in`` folder relative to the project root
    (i.e. the zenvi-backend folder).  Falls back to
    ``~/.config/zenvi/directors/built_in``.
    """
    backend_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    candidate = os.path.join(backend_root, "directors", "built_in")
    if os.path.isdir(candidate):
        return candidate
    return os.path.expanduser("~/.config/zenvi/directors/built_in")


class DirectorLoader:
    def __init__(self, builtin_dir: Optional[str] = None, user_dir: Optional[str] = None):
        self.builtin_dir = builtin_dir or _default_builtin_dir()
        self.user_dir = user_dir or os.path.expanduser("~/.config/zenvi/directors/")
        os.makedirs(self.builtin_dir, exist_ok=True)
        os.makedirs(self.user_dir, exist_ok=True)

    def load_director(self, director_id: str) -> Optional[Director]:
        builtin_path = os.path.join(self.builtin_dir, f"{director_id}.director")
        if os.path.exists(builtin_path):
            return self.load_director_from_file(builtin_path)
        user_path = os.path.join(self.user_dir, f"{director_id}.director")
        if os.path.exists(user_path):
            return self.load_director_from_file(user_path)
        log.warning("Director not found: %s", director_id)
        return None

    def load_director_from_file(self, filepath: str) -> Optional[Director]:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not self._validate_director_data(data):
                log.error("Invalid director file: %s", filepath)
                return None

            metadata = DirectorMetadata(
                id=data["id"],
                name=data["name"],
                version=data["version"],
                author=data["author"],
                description=data["description"],
                tags=data.get("tags", []),
                created_at=data.get("created_at", ""),
                updated_at=data.get("updated_at", ""),
            )

            pd = data["personality"]
            personality = DirectorPersonality(
                system_prompt=pd["system_prompt"],
                analysis_focus=pd.get("analysis_focus", []),
                critique_style=pd.get("critique_style", "constructive"),
                expertise_areas=pd.get("expertise_areas", []),
            )

            training = None
            if data.get("training"):
                training = DirectorTraining(
                    type=data["training"].get("type", "examples"),
                    data=data["training"].get("data", {}),
                )

            director = Director(
                metadata=metadata,
                personality=personality,
                training=training,
                settings=data.get("settings", {}),
            )
            log.info("Loaded director: %s (ID: %s)", director.name, director.id)
            return director

        except Exception as e:
            log.error("Failed to load director from %s: %s", filepath, e, exc_info=True)
            return None

    def list_available_directors(self) -> List[Director]:
        directors: List[Director] = []
        seen_ids: set = set()

        for d in (self.builtin_dir, self.user_dir):
            if not os.path.isdir(d):
                continue
            for filename in os.listdir(d):
                if not filename.endswith(".director"):
                    continue
                filepath = os.path.join(d, filename)
                director = self.load_director_from_file(filepath)
                if director and director.id not in seen_ids:
                    directors.append(director)
                    seen_ids.add(director.id)

        return directors

    def save_director(self, director: Director, user_dir: bool = True) -> bool:
        try:
            target_dir = self.user_dir if user_dir else self.builtin_dir
            os.makedirs(target_dir, exist_ok=True)
            filepath = os.path.join(target_dir, f"{director.id}.director")
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(director.to_dict(), f, indent=2, ensure_ascii=False)
            log.info("Saved director: %s to %s", director.name, filepath)
            return True
        except Exception as e:
            log.error("Failed to save director %s: %s", director.id, e, exc_info=True)
            return False

    def _validate_director_data(self, data: dict) -> bool:
        required = ("id", "name", "version", "author", "description", "personality")
        for field in required:
            if field not in data:
                log.error("Missing required field: %s", field)
                return False
        if "system_prompt" not in data.get("personality", {}):
            log.error("Missing system_prompt in personality")
            return False
        return True


_director_loader: Optional[DirectorLoader] = None


def get_director_loader() -> DirectorLoader:
    global _director_loader
    if _director_loader is None:
        _director_loader = DirectorLoader()
    return _director_loader
