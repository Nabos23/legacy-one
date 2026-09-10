from bson import ObjectId
from fastapi import HTTPException, status


def validate_object_id(widget_id: str) -> ObjectId:
    """Convert a string id to ObjectId or raise 404 if malformed."""
    if not ObjectId.is_valid(widget_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Widget not found.",
        )
    return ObjectId(widget_id)
