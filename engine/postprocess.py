from __future__ import annotations

from pathlib import Path
import numpy as np

from io_audio import read_audio, write_audio, peak_limit

STEM_NAMES_4 = ["vocals", "drums", "bass", "other"]


def _shape_spectrum(audio: np.ndarray, sr: int, stem: str) -> np.ndarray:
    if audio.size == 0:
        return audio
    n = audio.shape[0]
    freqs = np.fft.rfftfreq(n, d=1.0 / sr)
    gains = np.ones_like(freqs, dtype=np.float32)

    if stem == "vocals":
        gains[freqs < 120] *= 0.82
        gains[(freqs >= 3000) & (freqs <= 8000)] *= 1.05
        gains[freqs > 9000] *= 0.92
    elif stem == "drums":
        gains[(freqs >= 50) & (freqs <= 140)] *= 1.05
        gains[(freqs >= 2500) & (freqs <= 10000)] *= 1.03
    elif stem == "bass":
        gains[freqs < 160] *= 1.06
        gains[freqs > 2200] *= 0.88
    else:  # other
        gains[freqs < 90] *= 0.94
        gains[freqs > 7000] *= 0.97

    out = np.empty_like(audio, dtype=np.float32)
    for ch in range(audio.shape[1]):
        spec = np.fft.rfft(audio[:, ch])
        shaped = spec * gains
        out[:, ch] = np.fft.irfft(shaped, n=n).astype(np.float32)
    return out


def _vocal_light_denoise(audio: np.ndarray) -> np.ndarray:
    if audio.size == 0:
        return audio
    rms = float(np.sqrt(np.mean(np.square(audio))) + 1e-9)
    gate = 0.08 * rms
    out = audio.copy()
    mask = np.abs(out) < gate
    out[mask] *= 0.6
    return out.astype(np.float32)


def _normalize_rms(audio: np.ndarray, target_rms: float) -> np.ndarray:
    cur = float(np.sqrt(np.mean(np.square(audio))) + 1e-9)
    if cur <= 1e-8:
        return audio
    gain = target_rms / cur
    # Prevent extreme gain swings.
    gain = min(2.0, max(0.5, gain))
    return (audio * gain).astype(np.float32)


def residual_correction_adaptive(mix: np.ndarray, stems: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    """
    Distribute residual to all stems proportional to instantaneous stem energy.
    This avoids forcing all mismatch into "other".
    """
    if not stems:
        return stems

    t = min([mix.shape[0]] + [s.shape[0] for s in stems.values()])
    c = min([mix.shape[1]] + [s.shape[1] for s in stems.values()])
    mix_c = mix[:t, :c]
    names = list(stems.keys())
    stem_stack = np.stack([stems[n][:t, :c] for n in names], axis=0).astype(np.float32)
    summed = np.sum(stem_stack, axis=0)
    residual = mix_c - summed

    energy = np.abs(stem_stack) + 1e-6
    energy_sum = np.sum(energy, axis=0, keepdims=True)
    weights = energy / energy_sum
    stem_stack = stem_stack + weights * residual[np.newaxis, :, :]

    for i, name in enumerate(names):
        stems[name] = stem_stack[i]
    return stems


def simple_vocal_fusion(base_vocals: np.ndarray, refined_vocals: np.ndarray, mix_ratio: float = 0.65) -> np.ndarray:
    t = min(base_vocals.shape[0], refined_vocals.shape[0])
    c = min(base_vocals.shape[1], refined_vocals.shape[1])
    a = base_vocals[:t, :c]
    b = refined_vocals[:t, :c]
    blend = (mix_ratio * b + (1.0 - mix_ratio) * a).astype(np.float32)
    return blend


def postprocess_folder(
    input_mix_path: Path,
    stems_folder: Path,
    out_folder: Path,
    do_residual: bool = True,
    do_peak_limit: bool = True,
    refined_vocals_path: Path | None = None,
) -> None:
    mix, sr = read_audio(input_mix_path)
    stems: dict[str, np.ndarray] = {}
    for name in STEM_NAMES_4:
        p = stems_folder / f"{name}.wav"
        if p.exists():
            a, _ = read_audio(p)
            stems[name] = a

    if refined_vocals_path and refined_vocals_path.exists() and "vocals" in stems:
        v2, _ = read_audio(refined_vocals_path)
        stems["vocals"] = simple_vocal_fusion(stems["vocals"], v2, mix_ratio=0.65)

    if do_residual:
        stems = residual_correction_adaptive(mix, stems)

    # Stem-specific cleanup and tonal shaping.
    for name in list(stems.keys()):
        audio = stems[name]
        if name == "vocals":
            audio = _vocal_light_denoise(audio)
        audio = _shape_spectrum(audio, sr, name)
        if name == "vocals":
            audio = _normalize_rms(audio, target_rms=0.12)
        elif name == "drums":
            audio = _normalize_rms(audio, target_rms=0.13)
        elif name == "bass":
            audio = _normalize_rms(audio, target_rms=0.11)
        else:
            audio = _normalize_rms(audio, target_rms=0.12)

        if do_peak_limit:
            audio = peak_limit(audio, peak=0.985)
        stems[name] = audio.astype(np.float32)

    out_folder.mkdir(parents=True, exist_ok=True)
    for name, audio in stems.items():
        write_audio(out_folder / f"{name}.wav", audio, sr)
