from __future__ import annotations
from pathlib import Path
import shutil
import subprocess

def run_demucs_mlx(input_path: Path, output_root: Path, stems: int = 4) -> Path:
    """
    Runs demucs-mlx. Returns the folder that contains the stem wavs.
    IMPORTANT: CLI args may vary; adjust if needed for your installed version.
    """
    output_root.mkdir(parents=True, exist_ok=True)

    if stems == 2:
        cmd = ["demucs-mlx", "--two-stems", "vocals", "-o", str(output_root), str(input_path)]
    else:
        cmd = ["demucs-mlx", "-o", str(output_root), str(input_path)]

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError((proc.stdout or "")[-400:] + "\n" + (proc.stderr or "")[-400:])

    stem_files = ["vocals.wav", "drums.wav", "bass.wav", "other.wav"]
    candidates = []
    for p in output_root.rglob("vocals.wav"):
        folder = p.parent
        if all((folder / f).exists() for f in stem_files):
            candidates.append(folder)

    if not candidates:
        raise RuntimeError("Could not locate stems folder in demucs output.")
    candidates.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    return candidates[0]

def copy_stems(stems_folder: Path, out_folder: Path) -> None:
    out_folder.mkdir(parents=True, exist_ok=True)
    for name in ["vocals.wav", "drums.wav", "bass.wav", "other.wav"]:
        src = stems_folder / name
        if src.exists():
            shutil.copy2(src, out_folder / name)
