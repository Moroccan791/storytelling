"""Music, sound effects and mixing for the on-demand formats.

Everything here is synthesised with numpy - no sample library, no licence
questions. The bed is a slow chord pad, the effects are short synthetic
transients, and the music is side-chain ducked under the narration.

Levels: the bed sits ~26 dB under the voice before ducking, ducking takes it
a further ~9 dB while speech is present. The final mix goes through ffmpeg
loudnorm in build.py, so these are relative, not absolute.
"""
from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

RATE = 48000


# ---------------------------------------------------------------- helpers

def midi_hz(m: float) -> float:
    return 440.0 * 2.0 ** ((m - 69) / 12.0)


def _env_ar(n: int, attack: float, release: float, rate: int = RATE) -> np.ndarray:
    """Attack/release envelope across n samples."""
    a = max(1, int(attack * rate))
    r = max(1, int(release * rate))
    e = np.ones(n, dtype=np.float32)
    if a + r < n:
        e[:a] = np.linspace(0, 1, a) ** 2
        e[n - r:] = np.linspace(1, 0, r) ** 2
    else:  # too short: a bell
        e = np.hanning(n).astype(np.float32)
    return e


def _lowpass(x: np.ndarray, cutoff: float, rate: int = RATE) -> np.ndarray:
    spec = np.fft.rfft(x)
    freqs = np.fft.rfftfreq(len(x), d=1.0 / rate)
    mask = np.clip(1.0 - (freqs / cutoff) ** 2, 0, 1)
    return np.fft.irfft(spec * mask, n=len(x)).astype(np.float32)


def _noise(n: int, rng: np.random.Generator) -> np.ndarray:
    return rng.normal(0, 1, n).astype(np.float32)


def _bandpass(x: np.ndarray, lo: float, hi: float, rate: int = RATE) -> np.ndarray:
    spec = np.fft.rfft(x)
    freqs = np.fft.rfftfreq(len(x), d=1.0 / rate)
    mask = ((freqs >= lo) & (freqs <= hi)).astype(np.float32)
    # soften the edges so it does not ring
    mask = np.convolve(mask, np.ones(31) / 31, mode="same")
    return np.fft.irfft(spec * mask, n=len(x)).astype(np.float32)


def _place(buf: np.ndarray, clip: np.ndarray, start: float, gain: float = 1.0, rate: int = RATE):
    i = int(start * rate)
    if i >= len(buf):
        return
    j = min(len(buf), i + len(clip))
    buf[i:j] += clip[: j - i] * gain


# ---------------------------------------------------------------- music

# Chord voicings as MIDI note numbers. story = warm minor, facts = neutral.
PROGRESSIONS = {
    "story": [[45, 57, 60, 64], [41, 53, 57, 60], [48, 60, 64, 67], [43, 55, 59, 62]],
    "facts": [[45, 57, 60, 64], [40, 52, 55, 59], [41, 53, 57, 60], [43, 55, 59, 62]],
    "warm":  [[45, 57, 60, 64], [48, 60, 64, 67], [41, 53, 57, 60], [43, 55, 59, 62]],
}


def music_bed(dur: float, mood: str = "story", seed: int = 3, rate: int = RATE) -> np.ndarray:
    """A slow chord pad for `dur` seconds. Quiet and unobtrusive."""
    rng = np.random.default_rng(seed)
    n = int(dur * rate)
    out = np.zeros(n, dtype=np.float32)
    prog = PROGRESSIONS.get(mood, PROGRESSIONS["story"])

    # 8 chords across the video, each held long with slow overlap.
    bars = max(4, min(8, int(round(dur / 4.5))))
    step = dur / bars
    for b in range(bars + 1):
        chord = prog[b % len(prog)]
        start = b * step
        length = step * 1.45                      # overlap into the next chord
        m = int(length * rate)
        if m < 32:
            continue
        voice = np.zeros(m, dtype=np.float32)
        for k, note in enumerate(chord):
            f = midi_hz(note + 12)                # pads sit mid-register
            for det in (-0.11, 0.0, 0.13):        # gentle chorus
                ff = f * (1 + det / 100)
                ph = rng.uniform(0, 2 * np.pi)
                voice += (0.5 / (k + 1.6)) * np.sin(
                    2 * np.pi * ff * np.arange(m) / rate + ph).astype(np.float32)
                # slow vibrato makes it breathe
                voice *= 1.0 + 0.0025 * np.sin(2 * np.pi * 0.13 * np.arange(m) / rate)
        # root one octave down, felt more than heard
        root = midi_hz(chord[0] - 12)
        voice += 0.42 * np.sin(2 * np.pi * root * np.arange(m) / rate).astype(np.float32)
        voice *= _env_ar(m, attack=min(2.6, length * 0.5), release=min(2.6, length * 0.5), rate=rate)
        _place(out, voice, start, gain=0.20, rate=rate)

    # air: very quiet filtered noise so it is not sterile
    air = _bandpass(_noise(n, rng), 900, 5200, rate) * 0.006
    out += air
    # slow swell
    lfo = 1.0 + 0.10 * np.sin(2 * np.pi * 0.055 * np.arange(n) / rate + 0.6)
    out *= lfo
    out = _lowpass(out, 3600, rate)
    peak = float(np.max(np.abs(out))) or 1.0
    return (out / peak * 0.30).astype(np.float32)


# ---------------------------------------------------------------- effects

def sfx_whoosh(dur: float = 0.30, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    n = int(dur * RATE)
    t = np.arange(n) / RATE
    x = _noise(n, rng)
    # sweep the band up then down
    sweep = 500 + 2600 * np.sin(np.pi * t / max(dur, 1e-6))
    out = np.zeros(n, dtype=np.float32)
    for lo, hi, a in ((300, 1200, 0.5), (900, 2600, 0.9), (2200, 5200, 0.5)):
        out += _bandpass(x, lo, hi) * a
    out *= _env_ar(n, 0.10 * dur, 0.75 * dur)
    out *= (sweep / sweep.max()).astype(np.float32)
    return (out / (np.max(np.abs(out)) or 1) * 0.5).astype(np.float32)


def sfx_typing(dur: float = 0.5, seed: int = 0) -> np.ndarray:
    """One soft key click. build.py strings these together under a headline."""
    rng = np.random.default_rng(seed)
    n = int(0.045 * RATE)
    click = _bandpass(_noise(n, rng), 1400, 4600)
    click *= np.exp(-np.arange(n) / (0.004 * RATE)).astype(np.float32)
    thud = np.sin(2 * np.pi * 220 * np.arange(n) / RATE).astype(np.float32)
    thud *= np.exp(-np.arange(n) / (0.008 * RATE)).astype(np.float32)
    x = click * 0.8 + thud * 0.35
    return (x / (np.max(np.abs(x)) or 1) * 0.6).astype(np.float32)


def sfx_riser(dur: float = 1.1, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    n = int(dur * RATE)
    t = np.arange(n) / RATE
    x = _bandpass(_noise(n, rng), 400, 5000)
    x *= (t / dur).astype(np.float32) ** 2
    tone = np.sin(2 * np.pi * (180 + 420 * (t / dur) ** 2) * t).astype(np.float32) * 0.25
    out = x * 0.7 + tone
    out *= _env_ar(n, dur * 0.85, dur * 0.12)
    return (out / (np.max(np.abs(out)) or 1) * 0.42).astype(np.float32)


def sfx_thud(dur: float = 0.30, seed: int = 0) -> np.ndarray:
    n = int(dur * RATE)
    t = np.arange(n) / RATE
    body = np.sin(2 * np.pi * (74 - 22 * t / dur).clip(30) * t).astype(np.float32)
    body *= np.exp(-t / 0.06).astype(np.float32)
    return (body / (np.max(np.abs(body)) or 1) * 0.7).astype(np.float32)


def sfx_shimmer(dur: float = 1.4, seed: int = 0) -> np.ndarray:
    """Bell-like reveal. Used on twists and the decisive fact."""
    rng = np.random.default_rng(seed)
    n = int(dur * RATE)
    t = np.arange(n) / RATE
    out = np.zeros(n, dtype=np.float32)
    base = midi_hz(69)  # A4
    for i, (mult, g, dec) in enumerate([(1.0, 1.0, 0.55), (2.0, 0.5, 0.40), (3.0, 0.28, 0.30),
                                        (4.01, 0.16, 0.22), (5.43, 0.10, 0.18)]):
        out += g * np.sin(2 * np.pi * base * mult * t).astype(np.float32) * np.exp(-t / dec)
    out *= _env_ar(n, 0.004, dur * 0.5)
    return (out / (np.max(np.abs(out)) or 1) * 0.5).astype(np.float32)


EFFECTS = {"whoosh": sfx_whoosh, "typing": sfx_typing, "riser": sfx_riser,
           "thud": sfx_thud, "shimmer": sfx_shimmer}


# ---------------------------------------------------------------- mixing

def _envelope(x: np.ndarray, rate: int = RATE, win: float = 0.12) -> np.ndarray:
    """Cheap speech envelope: block-max then smooth then upsample.
    A per-sample filter loop over 1.7M samples is far too slow in python."""
    step = 256
    blocks = len(x) // step
    if blocks < 2:
        return np.abs(x)
    peak = np.abs(x[: blocks * step]).reshape(blocks, step).max(axis=1)
    k = max(1, int(win * rate / step))
    peak = np.convolve(peak, np.ones(k) / k, mode="same")
    return np.interp(np.arange(len(x)), np.arange(blocks) * step, peak).astype(np.float32)


def duck(music: np.ndarray, voice: np.ndarray, *, depth_db: float = 9.0,
         lookahead: float = 0.05, rate: int = RATE) -> np.ndarray:
    """Pull the music down while the voice is talking."""
    n = min(len(music), len(voice))
    env = _envelope(voice[:n], rate)
    ref = np.percentile(env, 97) or 1.0
    env = np.clip(env / ref, 0, 1)
    env = np.roll(np.clip(env * 1.6, 0, 1), -int(lookahead * rate))  # duck slightly early
    gain = (10 ** (-depth_db / 20.0)) ** env
    out = music[:n] * gain
    if len(music) > n:
        out = np.concatenate([out, music[n:]])
    return out.astype(np.float32)


def mix(dur: float, voice: np.ndarray, music: np.ndarray | None = None, *,
        voice_gain: float = 1.0, music_db: float = -26.0, duck_db: float = 9.0,
        events: list[tuple[float, str, float]] | None = None,
        rate: int = RATE) -> np.ndarray:
    """Build the final mono mix. `events` are (time, effect, gain_db)."""
    n = int(dur * rate)
    out = np.zeros(n, dtype=np.float32)

    v = voice[:n]
    out[: len(v)] += v * voice_gain

    if music is not None and len(music):
        m = music[:n]
        if len(m) < n:
            m = np.concatenate([m, np.zeros(n - len(m), dtype=np.float32)])
        bed = duck(m, v, depth_db=duck_db, rate=rate)
        out += bed * (10 ** (music_db / 20.0))

    for i, (t, kind, gain_db) in enumerate(events or []):
        if kind == "typing":
            # a short run of clicks rather than a single hit
            for k in range(3):
                _place(out, EFFECTS["typing"](seed=i * 13 + k), t + k * 0.052,
                       gain=10 ** (gain_db / 20.0), rate=rate)
        else:
            fn = EFFECTS.get(kind)
            if fn is None:
                raise ValueError(f"unknown effect {kind!r}")
            _place(out, fn(seed=i * 7), t, gain=10 ** (gain_db / 20.0), rate=rate)

    peak = float(np.max(np.abs(out)))
    if peak > 0.99:  # keep loudnorm some headroom
        out *= 0.99 / peak
    return out


def write_wav(path: str | Path, audio: np.ndarray, rate: int = RATE) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    x = np.clip(audio, -1.0, 1.0)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes((x * 32767.0).astype("<i2").tobytes())
    return path


def read_wav(path: str | Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as w:
        rate = w.getframerate()
        raw = w.readframes(w.getnframes())
    x = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    return x, rate
