from __future__ import annotations
from pathlib import Path
import numpy as np
import soundfile as sf

def read_audio(path: Path) -> tuple[np.ndarray, int]:
    """
    Returns audio as float32 array shape [T, C] and sample rate.
    """
    audio, sr = sf.read(str(path), always_2d=True, dtype="float32")
    return audio, sr

def write_audio(path: Path, audio: np.ndarray, sr: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    audio = np.nan_to_num(audio, nan=0.0, posinf=0.0, neginf=0.0).astype("float32")
    sf.write(str(path), audio, sr)

def peak_limit(audio: np.ndarray, peak: float = 0.999) -> np.ndarray:
    m = float(np.max(np.abs(audio))) if audio.size else 0.0
    if m <= peak or m == 0.0:
        return audio
    return (audio * (peak / m)).astype("float32")
