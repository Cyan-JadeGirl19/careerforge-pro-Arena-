"""Private document storage for reference letters/lists.

Private by default, local to the app. Encryption at rest and object
storage are part of the production storage phase; the paths are kept
opaque (uuid-named) so filenames never leak personal data.
"""
import os
import re
import uuid
from pathlib import Path

from ..config import get_settings

ALLOWED = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
}
MAX_SIZE = 5 * 1024 * 1024  # 5 MB


def _storage_root() -> Path:
    root = Path(get_settings().database_url.replace("sqlite:///", ""))
    if str(root) in ("", ":memory:"):
        root = Path.cwd() / "storage"
    else:
        root = root.parent / "storage"
    root.mkdir(parents=True, exist_ok=True)
    return root


def save_document(profile_id: str, filename: str, data: bytes) -> tuple[str, str]:
    """Store bytes; returns (opaque filename, content_type)."""
    if len(data) > MAX_SIZE:
        raise ValueError("File exceeds 5 MB.")
    ext = os.path.splitext(filename or "")[1].lower()
    if ext not in ALLOWED:
        raise ValueError("Only PDF, DOCX or TXT reference documents are supported.")
    name = f"{uuid.uuid4().hex}{ext}"
    folder = _storage_root() / profile_id
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_bytes(data)
    return str(folder / name), ALLOWED[ext]


def read_document(storage_path: str) -> bytes:
    p = Path(storage_path)
    if not p.is_file():
        raise FileNotFoundError("Document no longer exists.")
    return p.read_bytes()


def delete_document(storage_path: str) -> None:
    p = Path(storage_path)
    if p.is_file():
        p.unlink()


def delete_profile_storage(profile_id: str) -> None:
    folder = _storage_root() / profile_id
    if folder.is_dir():
        for f in folder.iterdir():
            if f.is_file():
                f.unlink()
        folder.rmdir()
