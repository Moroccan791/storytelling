"""Per-shot camera motion for the on-demand formats.

(Named `camera`, not `motion`, so it does not shadow the top-level `motion/`
package when a script is run as `python pipeline/build.py`.)

One image in, one moving shot out. Motion is always present (the formats
require it) and alternates direction between shots - the alternating is
enforced by the caller, `check.py` verifies it.

Moves: in | out | left | right | up | down
Every move is eased (smoothstep keyframes) so it starts and stops, rather
than the linear `zoompan` ramp.

Reuses the depth proxy, easing and dust from `motion/motion.py` so there is
one implementation of the look.
"""
from __future__ import annotations

import math
import subprocess
import sys
from pathlib import Path

import cv2
import imageio_ffmpeg
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from motion.motion import FPS, H, W, Dust, depth_proxy, glow_mask, keyframes, lamp_level  # noqa: E402

FF = imageio_ffmpeg.get_ffmpeg_exe()

# Computing the depth proxy is the expensive part; do it once per image.
_DEPTH: dict[str, np.ndarray] = {}

ZOOM_IN, ZOOM_OUT = 1.085, 1.085
PAN = 0.045  # fraction of frame width travelled on a pan


def _keys(move: str):
    """(t, zoom, panx, pany, roll) keyframes for a move. Pan always rides a
    slight push so the frame never runs out of image."""
    if move == "in":
        return [(0.0, 1.0, 0, 0, 0.0), (1.0, ZOOM_IN, 0, 0, 0.0)]
    if move == "out":
        return [(0.0, ZOOM_OUT, 0, 0, 0.0), (1.0, 1.0, 0, 0, 0.0)]
    d = W * PAN
    if move == "left":
        return [(0.0, 1.06, d, 0, 0.0), (1.0, 1.06, -d, 0, 0.0)]
    if move == "right":
        return [(0.0, 1.06, -d, 0, 0.0), (1.0, 1.06, d, 0, 0.0)]
    e = H * PAN
    if move == "up":
        return [(0.0, 1.06, 0, e, 0.0), (1.0, 1.06, 0, -e, 0.0)]
    if move == "down":
        return [(0.0, 1.06, 0, -e, 0.0), (1.0, 1.06, 0, e, 0.0)]
    raise ValueError(f"unknown move {move!r}")


def _depth_for(src: Path) -> np.ndarray:
    key = str(src)
    if key not in _DEPTH:
        img = cv2.imread(str(src))
        if img is None:
            raise SystemExit(f"cannot read image {src}")
        if img.shape[:2] != (H, W):
            img = cv2.resize(img, (W, H), interpolation=cv2.INTER_LANCZOS4)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _DEPTH[key] = depth_proxy(gray)
    return _DEPTH[key]


def render_shot(src: str | Path, out: str | Path, dur: float, *, move: str = "in",
                parallax: float = 0.0, grain: float = 2.0, vignette: float = 0.32,
                dust: int = 0, seed: int = 0) -> Path:
    """Render one shot of `dur` seconds. `parallax` is the displacement in
    pixels at full depth separation (0 disables it)."""
    src, out = Path(src), Path(out)
    bgr = cv2.imread(str(src))
    if bgr is None:
        raise SystemExit(f"cannot read image {src}")
    if bgr.shape[:2] != (H, W):
        bgr = cv2.resize(bgr, (W, H), interpolation=cv2.INTER_LANCZOS4)
    bgr = bgr.astype(np.float32)

    depth = _depth_for(src) if parallax > 0 else None
    keys = _keys(move)
    n_frames = max(1, round(dur * FPS))

    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    cx, cy = W / 2.0, H / 2.0
    vig = 1.0 - vignette * ((xx - cx) ** 2 / cx ** 2 + (yy - cy) ** 2 / cy ** 2) / 2.0
    vig = np.clip(vig, 0, 1)[..., None]

    motes = Dust(dust, (cx, H * 0.28), 340.0, seed=seed) if dust else None
    rng = np.random.default_rng(seed + 991)

    proc = subprocess.Popen(
        [FF, "-nostdin", "-y", "-hide_banner", "-loglevel", "error",
         "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", str(FPS),
         "-i", "-", "-an", "-c:v", "libx264", "-preset", "fast", "-crf", "19",
         "-pix_fmt", "yuv420p", str(out)], stdin=subprocess.PIPE)

    for i in range(n_frames):
        p = i / max(1, n_frames - 1)
        z, px, py, roll = keyframes(keys, p)
        th = math.radians(roll)
        cos_t, sin_t = math.cos(th), math.sin(th)
        dx, dy = xx - cx - px, yy - cy - py
        mapx = (cx + (cos_t * dx - sin_t * dy) / z).astype(np.float32)
        mapy = (cy + (sin_t * dx + cos_t * dy) / z).astype(np.float32)

        if depth is not None:
            d = cv2.remap(depth, mapx, mapy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
            shift = -parallax * (d - 0.5) * math.sin(math.pi * p)
            mapx = mapx + shift
            mapy = mapy + shift * 0.35

        frame = cv2.remap(bgr, mapx, mapy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        if motes is not None:
            frame = motes.draw(frame, i / FPS, 1.0)
        if grain:
            frame += rng.normal(0, grain, (H, W, 1)).astype(np.float32)
        frame *= vig

        proc.stdin.write(np.clip(frame, 0, 255).astype(np.uint8).tobytes())

    proc.stdin.close()
    if proc.wait():
        raise SystemExit(f"ffmpeg failed writing {out}")
    return out
