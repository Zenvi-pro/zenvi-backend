"""
Face manager — face detection, recognition, and people database.
Ported from zenvi-core.
"""

import json
import os
import time
from typing import Dict, List, Any, Optional
from logger import log


class Person:
    def __init__(self, person_id: str, name: str = ""):
        self.person_id = person_id
        self.name = name
        self.face_encodings: List[Any] = []
        self.thumbnail_path: Optional[str] = None
        self.created_at = time.time()

    def to_dict(self):
        return {
            "person_id": self.person_id,
            "name": self.name,
            "thumbnail_path": self.thumbnail_path,
            "created_at": self.created_at,
        }


class FaceManager:
    """Manages face detection, recognition, and people database."""

    def __init__(self, data_dir: str = ""):
        self.data_dir = data_dir or os.path.join(os.path.expanduser("~"), ".zenvi", "faces")
        self.people: Dict[str, Person] = {}
        self.face_file_map: Dict[str, List[str]] = {}  # file_id -> list of person_ids
        self._load()

    def _db_path(self):
        return os.path.join(self.data_dir, "people.json")

    def _load(self):
        try:
            path = self._db_path()
            if os.path.exists(path):
                with open(path) as f:
                    data = json.load(f)
                for p_data in data.get("people", []):
                    p = Person(p_data["person_id"], p_data.get("name", ""))
                    p.thumbnail_path = p_data.get("thumbnail_path")
                    p.created_at = p_data.get("created_at", time.time())
                    self.people[p.person_id] = p
                self.face_file_map = data.get("face_file_map", {})
        except Exception as e:
            log.debug("Face DB load failed: %s", e)

    def _save(self):
        try:
            os.makedirs(self.data_dir, exist_ok=True)
            data = {
                "people": [p.to_dict() for p in self.people.values()],
                "face_file_map": self.face_file_map,
            }
            with open(self._db_path(), "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            log.error("Face DB save failed: %s", e)

    def add_person(self, person_id: str, name: str = "") -> Person:
        p = Person(person_id, name)
        self.people[person_id] = p
        self._save()
        return p

    def get_person(self, person_id: str) -> Optional[Person]:
        return self.people.get(person_id)

    def list_people(self) -> List[Dict[str, Any]]:
        return [p.to_dict() for p in self.people.values()]

    def rename_person(self, person_id: str, name: str) -> bool:
        p = self.people.get(person_id)
        if p:
            p.name = name
            self._save()
            return True
        return False

    def delete_person(self, person_id: str) -> bool:
        if person_id in self.people:
            del self.people[person_id]
            for fid in list(self.face_file_map.keys()):
                self.face_file_map[fid] = [pid for pid in self.face_file_map[fid] if pid != person_id]
            self._save()
            return True
        return False

    def associate_face_with_file(self, file_id: str, person_id: str):
        if file_id not in self.face_file_map:
            self.face_file_map[file_id] = []
        if person_id not in self.face_file_map[file_id]:
            self.face_file_map[file_id].append(person_id)
            self._save()

    def get_faces_for_file(self, file_id: str) -> List[str]:
        return self.face_file_map.get(file_id, [])

    def get_statistics(self) -> Dict[str, Any]:
        return {"total_people": len(self.people), "total_associations": sum(len(v) for v in self.face_file_map.values())}


_instance: Optional[FaceManager] = None


def get_face_manager() -> FaceManager:
    global _instance
    if _instance is None:
        _instance = FaceManager()
    return _instance
