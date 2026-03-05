from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict
import time
import uuid
import threading

from demucs_runner import run_demucs_mlx, copy_stems
from postprocess import postprocess_folder

@dataclass
class Job:
    id: str
    input_path: Path
    output_dir: Path
    stems: int
    preset: str

    status: str = "queued"          # queued | running | done | error
    progress: float = 0.0
    message: str = ""
    created_at: float = field(default_factory=time.time)
    finished_at: Optional[float] = None
    error: Optional[str] = None

class JobStore:
    def __init__(self) -> None:
        self._jobs: Dict[str, Job] = {}
        self._lock = threading.Lock()

    def create(self, input_path: Path, output_dir: Path, stems: int, preset: str) -> Job:
        job = Job(id=str(uuid.uuid4()), input_path=input_path, output_dir=output_dir, stems=stems, preset=preset)
        with self._lock:
            self._jobs[job.id] = job
        return job

    def get(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(job_id)

STORE = JobStore()

def run_job(job: Job) -> None:
    job.status = "running"
    job.progress = 0.02
    job.message = "Preparing…"

    try:
        do_post = job.preset in ["best", "vocal_boost"]
        do_residual = job.preset in ["best", "vocal_boost"]

        job.message = "Running separation…"
        job.progress = 0.10

        temp_root = job.output_dir / "_engine_temp"
        stems_folder = run_demucs_mlx(job.input_path, temp_root, stems=job.stems)

        job.progress = 0.75
        job.message = "Post-processing…"

        out_stems = job.output_dir / "stems"
        out_stems.mkdir(parents=True, exist_ok=True)

        if not do_post:
            copy_stems(stems_folder, out_stems)
        else:
            postprocess_folder(
                input_mix_path=job.input_path,
                stems_folder=stems_folder,
                out_folder=out_stems,
                do_residual=do_residual,
                do_peak_limit=True,
                refined_vocals_path=None,
            )

        job.progress = 1.0
        job.status = "done"
        job.message = "Done."
        job.finished_at = time.time()

    except Exception as e:
        job.status = "error"
        job.error = str(e)
        job.message = "Error."
        job.finished_at = time.time()
