from bson import ObjectId
from fastapi import HTTPException, status


def validate_object_id(project_id: str) -> ObjectId:
    """Convert a string id to ObjectId or raise 404 if malformed."""
    if not ObjectId.is_valid(project_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )
    return ObjectId(project_id)
