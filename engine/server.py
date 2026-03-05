from __future__ import annotations
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pathlib import Path
import threading

from jobs import STORE, run_job

app = FastAPI(title="Moises Local Engine", version="0.2.0")

class SeparateRequest(BaseModel):
    input_path: str
    output_dir: str
    stems: int = 4                # 2 or 4
    preset: str = "best"          # fast | best | vocal_boost

class JobResponse(BaseModel):
    id: str
    status: str
    progress: float
    message: str
    output_dir: str
    stems_dir: str
    preset: str
    error: str | None = None

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/separate", response_model=JobResponse)
def separate(req: SeparateRequest):
    inp = Path(req.input_path).expanduser().resolve()
    out = Path(req.output_dir).expanduser().resolve()

    if not inp.exists():
        raise HTTPException(status_code=400, detail="input_path does not exist")

    if req.preset not in ["fast", "best", "vocal_boost"]:
        raise HTTPException(status_code=400, detail="invalid preset")

    if req.stems not in [2, 4]:
        raise HTTPException(status_code=400, detail="invalid stems")

    out.mkdir(parents=True, exist_ok=True)
    job = STORE.create(inp, out, stems=req.stems, preset=req.preset)

    t = threading.Thread(target=run_job, args=(job,), daemon=True)
    t.start()

    stems_dir = out / "stems"
    return JobResponse(
        id=job.id,
        status=job.status,
        progress=job.progress,
        message=job.message,
        output_dir=str(job.output_dir),
        stems_dir=str(stems_dir),
        preset=job.preset,
        error=job.error
    )

@app.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: str):
    job = STORE.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    stems_dir = job.output_dir / "stems"
    return JobResponse(
        id=job.id,
        status=job.status,
        progress=job.progress,
        message=job.message,
        output_dir=str(job.output_dir),
        stems_dir=str(stems_dir),
        preset=job.preset,
        error=job.error
    )
