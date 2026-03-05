from __future__ import annotations
from pathlib import Path
import numpy as np

from io_audio import read_audio, write_audio, peak_limit

STEM_NAMES_4 = ["vocals", "drums", "bass", "other"]

def residual_correction(mix: np.ndarray, stems: dict[str, np.ndarray], target: str = "other") -> dict[str, np.ndarray]:
    """
    Enforce mix ≈ sum(stems) by adding residual to a target stem (default: other).
    """
    T = mix.shape[0]
    C = mix.shape[1]
    acc = np.zeros((T, C), dtype="float32")
    for s in stems.values():
        acc[: min(T, s.shape[0]), : min(C, s.shape[1])] += s[:T, :C]

    residual = mix - acc
    if target in stems:
        stems[target] = (stems[target] + residual).astype("float32")
    else:
        stems[target] = residual.astype("float32")
    return stems

def simple_vocal_fusion(base_vocals: np.ndarray, refined_vocals: np.ndarray, mix_ratio: float = 0.65) -> np.ndarray:
    """
    Placeholder fusion: weighted blend.
    Later we can do band-limited blending; keep the interface stable.
    """
    T = min(base_vocals.shape[0], refined_vocals.shape[0])
    C = min(base_vocals.shape[1], refined_vocals.shape[1])
    a = base_vocals[:T, :C]
    b = refined_vocals[:T, :C]
    return (mix_ratio * b + (1.0 - mix_ratio) * a).astype("float32")

def postprocess_folder(
    input_mix_path: Path,
    stems_folder: Path,
    out_folder: Path,
    do_residual: bool = True,
    do_peak_limit: bool = True,
    refined_vocals_path: Path | None = None,
) -> None:
    """
    Reads stems from stems_folder, applies Phase-2 postprocessing, writes to out_folder.
    """
    mix, sr = read_audio(input_mix_path)

    stems: dict[str, np.ndarray] = {}
    for name in STEM_NAMES_4:
        p = stems_folder / f"{name}.wav"
        if p.exists():
            a, sr2 = read_audio(p)
            stems[name] = a

    if refined_vocals_path and refined_vocals_path.exists() and "vocals" in stems:
        v2, _ = read_audio(refined_vocals_path)
        stems["vocals"] = simple_vocal_fusion(stems["vocals"], v2, mix_ratio=0.65)

    if do_residual:
        stems = residual_correction(mix, stems, target="other")

    if do_peak_limit:
        for k in list(stems.keys()):
            stems[k] = peak_limit(stems[k], peak=0.999)

    out_folder.mkdir(parents=True, exist_ok=True)
    for k, audio in stems.items():
        write_audio(out_folder / f"{k}.wav", audio, sr)
