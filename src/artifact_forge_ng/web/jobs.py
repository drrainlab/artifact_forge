"""Background jobs — CAD builds must never block the cockpit.

``JobRunner`` is the seam: ThreadJobRunner today; the signatures allow a
ProcessJobRunner later (OCC can hang or crash in ways a thread cannot
contain) without touching the API layer.
"""

from __future__ import annotations

import threading
import traceback
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class Job:
    id: str
    kind: str
    status: str = "running"  # running | done | failed
    log: list[str] = field(default_factory=list)
    result: Any = None
    error: dict[str, Any] | None = None  # a FindingViewModel-shaped error

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "status": self.status,
            "log": list(self.log),
            "result": self.result,
            "error": self.error,
        }


class JobRunner:
    """Interface. submit() returns a job id immediately; get() polls."""

    def submit(self, kind: str, fn: Callable[[Job], Any]) -> str:
        raise NotImplementedError

    def get(self, job_id: str) -> Job | None:
        raise NotImplementedError


class ThreadJobRunner(JobRunner):
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def submit(self, kind: str, fn: Callable[[Job], Any]) -> str:
        job = Job(id=uuid.uuid4().hex[:12], kind=kind)
        with self._lock:
            self._jobs[job.id] = job

        def run() -> None:
            from .serialize import error_finding

            try:
                job.result = fn(job)
                job.status = "done"
            except Exception as exc:  # noqa: BLE001 — jobs report, never raise
                job.status = "failed"
                report = getattr(exc, "report", None)
                job.result = report
                job.error = error_finding(str(exc), check=f"{kind}.failed")
                job.log.append(traceback.format_exc(limit=3))

        threading.Thread(target=run, daemon=True).start()
        return job.id

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)
