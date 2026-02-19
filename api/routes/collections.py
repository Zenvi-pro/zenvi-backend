"""
Collection management endpoints.
"""

from typing import List
from fastapi import APIRouter
from api.schemas import (
    CreateCollectionRequest, CollectionSchema, AddFileToCollectionRequest, StatusResponse,
)

router = APIRouter(prefix="/collections", tags=["collections"])


@router.get("", response_model=List[CollectionSchema])
def list_collections():
    """List all collections."""
    from core.managers.collections import get_collection_manager
    data = get_collection_manager().list_collections()
    return [CollectionSchema(**c) for c in data]


@router.post("", response_model=CollectionSchema)
def create_collection(req: CreateCollectionRequest):
    """Create a new collection."""
    from core.managers.collections import get_collection_manager
    c = get_collection_manager().create_collection(req.collection_id, req.name, req.collection_type)
    return CollectionSchema(**c.to_dict())


@router.get("/{collection_id}", response_model=CollectionSchema)
def get_collection(collection_id: str):
    """Get a collection by ID."""
    from core.managers.collections import get_collection_manager
    c = get_collection_manager().get_collection(collection_id)
    if not c:
        return CollectionSchema(collection_id=collection_id, name="Not Found")
    return CollectionSchema(**c.to_dict())


@router.delete("/{collection_id}", response_model=StatusResponse)
def delete_collection(collection_id: str):
    """Delete a collection."""
    from core.managers.collections import get_collection_manager
    ok = get_collection_manager().delete_collection(collection_id)
    return StatusResponse(success=ok, message="Deleted" if ok else "Not found")


@router.post("/{collection_id}/files", response_model=StatusResponse)
def add_file_to_collection(collection_id: str, req: AddFileToCollectionRequest):
    """Add a file to a manual collection."""
    from core.managers.collections import get_collection_manager
    ok = get_collection_manager().add_file_to_collection(collection_id, req.file_id)
    return StatusResponse(success=ok, message="Added" if ok else "Failed")


@router.get("/statistics/summary")
def collection_statistics():
    """Get collection statistics."""
    from core.managers.collections import get_collection_manager
    return get_collection_manager().get_statistics()
