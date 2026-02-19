"""
Face management endpoints.
"""

from typing import List
from fastapi import APIRouter
from api.schemas import PersonSchema, CreatePersonRequest, RenamePersonRequest, StatusResponse

router = APIRouter(prefix="/faces", tags=["faces"])


@router.get("/people", response_model=List[PersonSchema])
def list_people():
    """List all known people."""
    from core.managers.faces import get_face_manager
    return [PersonSchema(**p) for p in get_face_manager().list_people()]


@router.post("/people", response_model=PersonSchema)
def create_person(req: CreatePersonRequest):
    """Add a new person."""
    from core.managers.faces import get_face_manager
    p = get_face_manager().add_person(req.person_id, req.name)
    return PersonSchema(**p.to_dict())


@router.put("/people/{person_id}", response_model=StatusResponse)
def rename_person(person_id: str, req: RenamePersonRequest):
    """Rename a person."""
    from core.managers.faces import get_face_manager
    ok = get_face_manager().rename_person(person_id, req.name)
    return StatusResponse(success=ok, message="Renamed" if ok else "Person not found")


@router.delete("/people/{person_id}", response_model=StatusResponse)
def delete_person(person_id: str):
    """Delete a person."""
    from core.managers.faces import get_face_manager
    ok = get_face_manager().delete_person(person_id)
    return StatusResponse(success=ok, message="Deleted" if ok else "Person not found")


@router.get("/files/{file_id}")
def get_faces_for_file(file_id: str):
    """Get people detected in a file."""
    from core.managers.faces import get_face_manager
    return {"person_ids": get_face_manager().get_faces_for_file(file_id)}


@router.get("/statistics")
def face_statistics():
    """Get face/people statistics."""
    from core.managers.faces import get_face_manager
    return get_face_manager().get_statistics()
