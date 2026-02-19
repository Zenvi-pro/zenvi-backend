"""
Collection manager — smart/manual collections for media organization.
Ported from zenvi-core.
"""

import time
from enum import Enum
from typing import Dict, List, Any, Optional
from logger import log


class CollectionType(Enum):
    SMART = "smart"
    MANUAL = "manual"
    PERSON = "person"
    PRESET = "preset"


class FilterOperator(Enum):
    EQUALS = "equals"
    CONTAINS = "contains"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    IN = "in"
    NOT_IN = "not_in"


class CollectionRule:
    def __init__(self, field: str, operator: FilterOperator, value: Any):
        self.field = field
        self.operator = operator
        self.value = value

    def matches(self, data: Dict[str, Any]) -> bool:
        actual = self._resolve_field(data, self.field)
        if actual is None:
            return False
        if self.operator == FilterOperator.EQUALS:
            return actual == self.value
        if self.operator == FilterOperator.CONTAINS:
            if isinstance(actual, (list, str)):
                return self.value in actual
            return str(self.value) in str(actual)
        if self.operator == FilterOperator.GREATER_THAN:
            return actual > self.value
        if self.operator == FilterOperator.LESS_THAN:
            return actual < self.value
        if self.operator == FilterOperator.IN:
            return actual in self.value
        if self.operator == FilterOperator.NOT_IN:
            return actual not in self.value
        return False

    def _resolve_field(self, data, field_path):
        parts = field_path.split(".")
        current = data
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None
        return current

    def to_dict(self):
        return {"field": self.field, "operator": self.operator.value, "value": self.value}


class Collection:
    def __init__(self, collection_id: str, name: str, collection_type: CollectionType = CollectionType.MANUAL):
        self.collection_id = collection_id
        self.name = name
        self.collection_type = collection_type
        self.rules: List[CollectionRule] = []
        self.file_ids: List[str] = []  # manual
        self.created_at = time.time()

    def matches_file(self, file_data: Dict[str, Any]) -> bool:
        if self.collection_type == CollectionType.MANUAL:
            return file_data.get("id") in self.file_ids
        return all(rule.matches(file_data) for rule in self.rules)

    def to_dict(self):
        return {
            "collection_id": self.collection_id,
            "name": self.name,
            "type": self.collection_type.value,
            "rules": [r.to_dict() for r in self.rules],
            "file_ids": self.file_ids,
            "created_at": self.created_at,
        }


class CollectionManager:
    def __init__(self):
        self.collections: Dict[str, Collection] = {}

    def create_collection(self, collection_id: str, name: str, collection_type: str = "manual") -> Collection:
        ct = CollectionType(collection_type) if collection_type in [e.value for e in CollectionType] else CollectionType.MANUAL
        c = Collection(collection_id, name, ct)
        self.collections[collection_id] = c
        return c

    def get_collection(self, collection_id: str) -> Optional[Collection]:
        return self.collections.get(collection_id)

    def list_collections(self) -> List[Dict[str, Any]]:
        return [c.to_dict() for c in self.collections.values()]

    def delete_collection(self, collection_id: str) -> bool:
        if collection_id in self.collections:
            del self.collections[collection_id]
            return True
        return False

    def add_file_to_collection(self, collection_id: str, file_id: str) -> bool:
        c = self.collections.get(collection_id)
        if c and c.collection_type == CollectionType.MANUAL:
            if file_id not in c.file_ids:
                c.file_ids.append(file_id)
            return True
        return False

    def get_statistics(self) -> Dict[str, Any]:
        return {"total": len(self.collections)}


_instance: Optional[CollectionManager] = None


def get_collection_manager() -> CollectionManager:
    global _instance
    if _instance is None:
        _instance = CollectionManager()
    return _instance
