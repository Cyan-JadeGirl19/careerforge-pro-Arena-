"""In-process background jobs for long-running media work.

The Render free tier times out long HTTP responses, so enhancement and
format conversion run in worker threads; the client polls
`GET /jobs/video/{job_id}`. State is in-memory on purpose: media bytes
are safe in the database, so a restart only loses in-flight work
(which the UI simply re-triggers).
"""
from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field

_MAX_AGE_DONE = 3600  # keep finished jobs for 1 h
_MAX_AGE_ANY = 2 * 3600


@dataclass
class Job:
    kind: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: str = "running"  # running | done | failed
    phase: str = "starting"
    progress: float = 0.0
    result: dict | None = None
    error: str | None = None
    created_at: float = field(default_factory=time.time)

    def to_out(self) -> dict:
        return {
            "job_id": self.id,
            "kind": self.kind,
            "status": self.status,
            "phase": self.phase,
            "progress": round(self.progress, 2),
            "result": self.result,
            "error": self.error,
        }


_JOBS: dict[str, Job] = {}
_LOCK = threading.Lock()


def submit(kind: str, fn, *args, **kwargs) -> Job:
    """Run `fn(job, *args)` in a worker thread and track it."""
    job = Job(kind=kind)
    with _LOCK:
        _prune_locked()
        _JOBS[job.id] = job

    def _runner() -> None:
        try:
            fn(job, *args, **kwargs)
            if job.status == "running":
                job.status = "done"
        except Exception as exc:  # noqa: BLE001 - surfaced to the UI
            job.status = "failed"
            job.error = str(exc)[:500] or "processing failed"

    threading.Thread(target=_runner, daemon=True).start()
    return job


def get_job(job_id: str) -> Job | None:
    with _LOCK:
        job = _JOBS.get(job_id)
        if job is not None and job.status != "running":
            if time.time() - job.created_at > _MAX_AGE_DONE:
                _JOBS.pop(job_id, None)
                return None
        return job


def _prune_locked() -> None:
    now = time.time()
    for k in list(_JOBS):
        j = _JOBS[k]
        if now - j.created_at > _MAX_AGE_ANY:
            _JOBS.pop(k, None)
        elif j.status != "running" and now - j.created_at > _MAX_AGE_DONE:
            _JOBS.pop(k, None)
