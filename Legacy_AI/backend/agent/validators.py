from bson import ObjectId
from fastapi import HTTPException, status

def validate_object_id(agent_id: str) -> ObjectId:
    """Convert a string id to ObjectId or raise 404 if malformed."""
    if not ObjectId.is_valid(agent_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found.",
        )
    return ObjectId(agent_id)