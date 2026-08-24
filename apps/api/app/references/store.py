"""Reference document validation.

Documents are stored as bytes in the database (see ReferenceDocument)
so they survive ephemeral deploy filesystems. Production upgrade path:
encrypted object storage. Only PDF/DOCX/TXT up to 5 MB are accepted.
"""
import os

ALLOWED = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
}
MAX_SIZE = 5 * 1024 * 1024  # 5 MB


def _ext(filename: str) -> str:
    return os.path.splitext(filename or "")[1].lower()


def content_type_for(filename: str) -> str:
    ext = _ext(filename)
    if ext not in ALLOWED:
        raise ValueError("Only PDF, DOCX or TXT reference documents are supported.")
    return ALLOWED[ext]


def validate_document(filename: str, data: bytes) -> str:
    """Raise ValueError if the upload is not allowed; returns content type."""
    if len(data) > MAX_SIZE:
        raise ValueError("File exceeds 5 MB.")
    return content_type_for(filename)
