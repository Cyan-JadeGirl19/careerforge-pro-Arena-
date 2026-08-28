"""Chunked video upload sessions.

Why: Render's free tier kills any single HTTP request that runs long
(~100 s). A 2-3 minute video on a typical SA home connection takes
longer than that to upload as one request - which is exactly what
caused the "Upload failed (500)" reports. So the client splits the
file into ~5 MB chunks; each request is small and fast, the bytes are
streamed straight to a temp file (no multi-hundred-MB in-memory
buffer), and the final "complete" step probes and stores the file.

Sessions are in-memory with a 30-minute TTL and an unguessable id.
"""
from __future__ import annotations

import os
import tempfile
import time
import uuid
from dataclasses import dataclass, field

MAX_UPLOAD_BYTES = 150 * 1024 * 1024  # 150 MB
CHUNK_SIZE = 5 * 1024 * 1024  # 5 MB per request
TTL = 1800  # 30 minutes

ALLOWED_CONTENT_TYPES = {
    "video/webm", "video/mp4", "video/quicktime", "video/x-m4v", "video/mpeg",
}


class UploadError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


@dataclass
class UploadSession:
    video_id: str
    profile_id: str
    filename: str
    content_type: str
    expected_size: int
    temp_path: str
    received_bytes: int = 0
    received_chunks: int = 0
    created_at: float = field(default_factory=time.time)


_SESSIONS: dict[str, UploadSession] = {}


def _prune() -> None:
    now = time.time()
    for k in [k for k, s in _SESSIONS.items() if now - s.created_at > TTL]:
        s = _SESSIONS.pop(k)
        try:
            os.unlink(s.temp_path)
        except OSError:
            pass


def init_session(
    video_id: str,
    profile_id: str,
    filename: str,
    content_type: str,
    expected_size: int,
) -> tuple[str, UploadSession]:
    _prune()
    ct = (content_type or "").lower().split(";")[0].strip()
    if ct not in ALLOWED_CONTENT_TYPES:
        raise UploadError(
            "UNSUPPORTED_MEDIA_TYPE",
            "Unsupported file type. Upload MP4, WebM, MOV or M4V.",
            status=415,
        )
    if expected_size <= 0:
        raise UploadError("BAD_SIZE", "File size missing.", status=422)
    if expected_size > MAX_UPLOAD_BYTES:
        raise UploadError(
            "MEDIA_TOO_LARGE", "File exceeds the 150 MB limit.", status=413
        )
    upload_id = uuid.uuid4().hex
    fd, path = tempfile.mkstemp(suffix=".part", prefix="cfupload-")
    os.close(fd)
    session = UploadSession(
        video_id=video_id,
        profile_id=profile_id,
        filename=filename or "recording",
        content_type=ct,
        expected_size=expected_size,
        temp_path=path,
    )
    _SESSIONS[upload_id] = session
    return upload_id, session


def get_session(upload_id: str) -> UploadSession:
    session = _SESSIONS.get(upload_id)
    if session is None:
        raise UploadError("UPLOAD_NOT_FOUND", "Upload session not found (it may have expired).", status=404)
    if time.time() - session.created_at > TTL:
        _SESSIONS.pop(upload_id, None)
        try:
            os.unlink(session.temp_path)
        except OSError:
            pass
        raise UploadError("UPLOAD_EXPIRED", "Upload session expired - start again.", status=410)
    return session


def write_chunk(upload_id: str, index: int, data: bytes) -> UploadSession:
    session = get_session(upload_id)
    if index != session.received_chunks:
        raise UploadError(
            "CHUNK_OUT_OF_ORDER",
            f"Expected chunk {session.received_chunks}, got {index}.",
            status=409,
        )
    session.received_bytes += len(data)
    if session.received_bytes > MAX_UPLOAD_BYTES:
        raise UploadError("MEDIA_TOO_LARGE", "File exceeds the 150 MB limit.", status=413)
    with open(session.temp_path, "ab") as fh:
        fh.write(data)
    session.received_chunks += 1
    return session


def complete_session(upload_id: str) -> UploadSession:
    session = get_session(upload_id)
    if session.received_bytes != session.expected_size:
        raise UploadError(
            "INCOMPLETE",
            f"Received {session.received_bytes} of {session.expected_size} bytes - upload again.",
            status=409,
        )
    return session


def discard(upload_id: str) -> None:
    session = _SESSIONS.pop(upload_id, None)
    if session is not None:
        try:
            os.unlink(session.temp_path)
        except OSError:
            pass
