"""Constants for the db-connection package."""

# Keep inline schemas under MongoDB's 16 MB document limit (with margin).
# Larger schemas are offloaded to GridFS so the write never fails.
SCHEMA_INLINE_MAX_BYTES = 15 * 1024 * 1024

# GridFS bucket used to store oversized schemas.
SCHEMA_GRIDFS_BUCKET = "db_schemas"
