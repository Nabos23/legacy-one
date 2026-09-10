import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from backend.core.config import settings

# Magic-byte signatures for the image formats we accept. The client-supplied
# filename and Content-Type are never trusted — only the actual file bytes.
_SIGNATURES: dict[bytes, str] = {
    b"\x89PNG\r\n\x1a\n": "png",
    b"\xff\xd8\xff": "jpg",
    b"GIF87a": "gif",
    b"GIF89a": "gif",
}


def _sniff_image_extension(data: bytes) -> str | None:
    """Identify an image format from its magic bytes, or None if unrecognized."""
    for signature, ext in _SIGNATURES.items():
        if data.startswith(signature):
            return ext
    if len(data) >= 12 and data[0:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


async def save_image_upload(file: UploadFile, *, subdir: str) -> str:
    """Validate and persist an uploaded image to local disk.

    Returns the URL path (e.g. "/media/avatars/<uuid>.png") to store/serve.
    Raises HTTPException(400) if the upload isn't a recognized image or
    exceeds the configured size limit. The stored filename is always
    server-generated — the client's filename is never used as a path.
    """
    data = await file.read()
    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )
    if len(data) > settings.AVATAR_MAX_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Max size is {settings.AVATAR_MAX_SIZE_BYTES // (1024 * 1024)}MB.",
        )

    ext = _sniff_image_extension(data)
    if ext is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file type. Upload a PNG, JPEG, GIF, or WEBP image.",
        )

    directory = Path(settings.MEDIA_ROOT) / subdir
    directory.mkdir(parents=True, exist_ok=True)

    filename = f"{uuid.uuid4().hex}.{ext}"
    (directory / filename).write_bytes(data)

    return f"{settings.MEDIA_URL_PATH}/{subdir}/{filename}"


def delete_stored_upload(url_path: str | None) -> None:
    """Best-effort removal of a previously stored upload from local disk."""
    if not url_path or not url_path.startswith(settings.MEDIA_URL_PATH):
        return
    relative = url_path.removeprefix(settings.MEDIA_URL_PATH).lstrip("/")
    file_path = Path(settings.MEDIA_ROOT) / relative
    try:
        file_path.unlink(missing_ok=True)
    except OSError:
        pass

REPORTS_DIR = Path(__file__).resolve().parent.parent.parent / "backend" / "storage" / "reports"


def delete_report_file(filename: str | None) -> None:
    """Best-effort removal of a generated report file from local disk."""
    if not filename:
        return
    safe_name = Path(filename).name
    if not safe_name or safe_name != filename:
        # Path(filename).name stripping anything means the input tried to
        # traverse directories (e.g. "../../etc/passwd") -- refuse it.
        return
    file_path = REPORTS_DIR / safe_name
    try:
        file_path.unlink(missing_ok=True)
    except OSError:
        pass


def resolve_local_attachment_path(filename: str) -> str | None:
    """Resolve a filename to its real path in local report storage, or None.
    Swap this function's internals when moving to remote storage."""
    if not filename:
        return None
    safe_name = Path(filename).name
    if not safe_name or safe_name != filename:
        return None
    file_path = REPORTS_DIR / safe_name
    return str(file_path) if file_path.is_file() else None