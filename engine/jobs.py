from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, cast
import time
import uuid
import threading
import subprocess
import shutil
from datetime import timedelta

try:
    import psutil
except Exception:  # pragma: no cover - optional import fallback
    psutil = None

from demucs_runner import run_demucs_mlx, copy_stems
from postprocess import postprocess_folder

@dataclass
class Job:
    id: str
    input_path: Path
    output_dir: Path
    stems: int
    preset: str
    quality_mode: str
    model: Optional[str]
    ensemble_model: Optional[str]

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

    def create(
        self,
        input_path: Path,
        output_dir: Path,
        stems: int,
        preset: str,
        quality_mode: str,
        model: Optional[str],
        ensemble_model: Optional[str],
    ) -> Job:
        job = Job(
            id=str(uuid.uuid4()),
            input_path=input_path,
            output_dir=output_dir,
            stems=stems,
            preset=preset,
            quality_mode=quality_mode,
            model=model,
            ensemble_model=ensemble_model,
        )
        with self._lock:
            self._jobs[job.id] = job
        return job

    def get(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(job_id)

    def has_active(self) -> bool:
        with self._lock:
            return any(j.status in ("queued", "running") for j in self._jobs.values())

    def get_active(self) -> Optional[Job]:
        with self._lock:
            active = [j for j in self._jobs.values() if j.status in ("queued", "running")]
            if not active:
                return None
            active.sort(key=lambda j: j.created_at, reverse=True)
            return active[0]

STORE = JobStore()

def _is_demucs_cmdline(text: str) -> bool:
    lowered = text.lower()
    return (
        "demucs-mlx" in lowered
        or "demucs_mlx" in lowered
        or "demucs.separate" in lowered
        or " demucs " in f" {lowered} "
    )


def _fmt_elapsed(seconds: float) -> str:
    whole = max(0, int(seconds))
    return str(timedelta(seconds=whole))

def external_demucs_running() -> bool:
    """
    Detect ongoing demucs subprocesses even if they outlive/restart the API process.
    """
    if psutil is not None:
        try:
            for proc in psutil.process_iter(["name", "cmdline"]):
                cmdline = " ".join(proc.info.get("cmdline") or [])
                name = proc.info.get("name") or ""
                if _is_demucs_cmdline(f"{name} {cmdline}"):
                    return True
        except Exception:
            return False
        return False

    try:
        proc = subprocess.run(["ps", "-Ao", "command"], capture_output=True, text=True, check=False)
        out = proc.stdout or ""
        for line in out.splitlines():
            if _is_demucs_cmdline(line):
                return True
    except Exception:
        return False
    return False

def external_demucs_processes() -> list[dict[str, str]]:
    """
    Return running demucs processes with lightweight runtime metadata.
    """
    if psutil is not None:
        rows: list[dict[str, str]] = []
        try:
            now = time.time()
            for proc in psutil.process_iter(["pid", "create_time", "name", "cmdline"]):
                cmdline = " ".join(proc.info.get("cmdline") or [])
                name = proc.info.get("name") or ""
                full = f"{name} {cmdline}".strip()
                if not _is_demucs_cmdline(full):
                    continue
                created = float(proc.info.get("create_time") or now)
                rows.append(
                    {
                        "pid": str(proc.info.get("pid", "?")),
                        "etime": _fmt_elapsed(max(0.0, now - created)),
                        "command": full,
                    }
                )
        except Exception:
            return []
        return rows

    rows: list[dict[str, str]] = []
    try:
        proc = subprocess.run(
            ["ps", "-Ao", "pid=,etime=,command="],
            capture_output=True,
            text=True,
            check=False,
        )
        out = proc.stdout or ""
        for line in out.splitlines():
            line = line.strip()
            if not line:
                continue
            if not _is_demucs_cmdline(line):
                continue
            parts = line.split(None, 2)
            if len(parts) < 3:
                continue
            rows.append({"pid": parts[0], "etime": parts[1], "command": parts[2]})
    except Exception:
        return []
    return rows

def run_job(job: Job) -> None:
    job.status = "running"
    job.progress = 0.02
    job.message = "Preparing…"
    temp_root = job.output_dir / "_engine_temp"

    try:
        do_post = job.preset in ["best", "vocal_boost"] and job.stems == 4
        do_residual = job.preset in ["best", "vocal_boost"]

        job.message = "Running separation… this can take several minutes."
        job.progress = 0.10

        result: dict[str, object] = {}
        sep_state: dict[str, object] = {
            "progress": 0.10,
            "message": "Running separation… this can take several minutes.",
        }

        def _run_sep() -> None:
            def _on_progress(p: float, m: str) -> None:
                sep_state["progress"] = p
                sep_state["message"] = m

            result["stems_folder"] = run_demucs_mlx(
                job.input_path,
                temp_root,
                stems=job.stems,
                quality_mode=job.quality_mode,
                model=job.model,
                ensemble_model=job.ensemble_model,
                progress_cb=_on_progress,
            )

        worker = threading.Thread(target=_run_sep, daemon=True)
        worker.start()
        tick = 0
        while worker.is_alive():
            tick += 1
            p = float(sep_state.get("progress", 0.10))
            m = str(sep_state.get("message", "Running separation… this can take several minutes."))
            # Keep progress moving even when external model has no granular callback updates.
            floor_progress = min(0.88, 0.10 + tick * 0.004)
            job.progress = max(min(p, 0.88), floor_progress)
            job.message = m
            time.sleep(1.0)
        worker.join()

        stems_folder = result.get("stems_folder")
        if not stems_folder:
            raise RuntimeError("Separation failed before output was produced.")
        stems_folder = cast(Path, stems_folder)

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
    finally:
        try:
            if temp_root.exists():
                shutil.rmtree(temp_root, ignore_errors=True)
        except Exception:
            # Cleanup should never hide the main job outcome.
            pass
