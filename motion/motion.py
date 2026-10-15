"""Motion renderer - turn a still illustration into a moving shot.

What it does, frame by frame, on CPU:
  1. eased multi-keyframe camera (zoom / pan / roll), not a linear ramp
  2. 2.5D parallax: pixels are displaced by a depth proxy, so near things
     slide more than far things as the camera moves
  3. practical light: a radial lamp glow that flickers on its own schedule
  4. drifting dust motes, visible only inside the light
  5. film finish: grain, breathing exposure, vignette

Usage:
  python motion.py SRC.png OUT.mp4 PROFILE
Profiles: living | parallax | comparison
"""
import math, subprocess, sys
from pathlib import Path

import cv2
import imageio_ffmpeg
import numpy as np

W, H, FPS = 1080, 1920, 30
FF = imageio_ffmpeg.get_ffmpeg_exe()


def smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def keyframes(keys, p):
    """keys: [(t, zoom, panx, pany, roll)] with t in 0..1. Eased interpolation."""
    if p <= keys[0][0]:
        return keys[0][1:]
    if p >= keys[-1][0]:
        return keys[-1][1:]
    for (t0, *v0), (t1, *v1) in zip(keys, keys[1:]):
        if t0 <= p <= t1:
            f = smoothstep((p - t0) / (t1 - t0))
            return tuple(a + (b - a) * f for a, b in zip(v0, v1))
    return keys[-1][1:]


def depth_proxy(gray):
    """Cheap depth: blurred luminance (bright = lit/near) + screen height
    (low in frame = near). Good enough for small parallax displacements."""
    lum = cv2.GaussianBlur(gray, (0, 0), 45)
    lum = (lum - lum.min()) / (np.ptp(lum) + 1e-6)
    yramp = np.linspace(1.0, 0.0, H, dtype=np.float32)[:, None]
    d = 0.35 * lum + 0.65 * yramp
    d = cv2.GaussianBlur(d, (0, 0), 60)
    return (d - d.min()) / (np.ptp(d) + 1e-6)


def glow_mask(center, sigma):
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    r2 = (xx - center[0]) ** 2 + (yy - center[1]) ** 2
    return np.exp(-r2 / (2 * sigma * sigma))


def lamp_level(t, seed=0):
    """Slow warm breathing plus occasional flicker events."""
    rng = np.random.default_rng(seed + int(t * 7))
    base = 1.0 + 0.035 * math.sin(2 * math.pi * 0.35 * t + 1.1)
    spike = 0.0
    for ph in (1.7, 3.9, 5.4):
        if 0 <= t - ph < 0.18:
            spike = -0.10 * math.sin(math.pi * (t - ph) / 0.18)
    hum = 0.012 * math.sin(2 * math.pi * 47 * t + 0.4) * rng.choice([1, 1, 1, 2])
    return base + spike + hum


class Dust:
    """Motes drifting through the light cone."""

    def __init__(self, n, center, sigma, seed=7):
        rng = np.random.default_rng(seed)
        self.c = center
        self.sigma = sigma
        self.pos = np.stack([
            rng.normal(center[0], sigma * 0.55, n),
            rng.normal(center[1], sigma * 0.5, n),
        ], axis=1)
        self.vel = np.stack([
            rng.normal(0, 4.0, n),
            rng.normal(7.0, 3.0, n),
        ], axis=1)
        self.size = rng.uniform(0.7, 2.6, n)
        self.alpha = rng.uniform(0.18, 0.75, n)

    def draw(self, frame, t, heat):
        # Paint each mote into its own small patch - building a full-frame mask
        # per particle is what makes this 20x slower than it needs to be.
        out = frame
        tint = np.array([0.55, 0.78, 1.0], dtype=np.float32) * 255 * 0.30
        phase = np.arange(len(self.pos))
        p = self.pos + self.vel * t
        p[:, 0] += 3.0 * np.sin(0.5 * t + phase)
        for (x, y), s, a in zip(p, self.size, self.alpha):
            rad = s * 3.4
            if not (-rad <= x < W + rad and -rad <= y < H + rad):
                continue
            r = int(rad) + 1
            x0, x1 = max(0, int(x) - r), min(W, int(x) + r + 1)
            y0, y1 = max(0, int(y) - r), min(H, int(y) + r + 1)
            if x0 >= x1 or y0 >= y1:
                continue
            gy = np.arange(y0, y1, dtype=np.float32)[:, None] - y
            gx = np.arange(x0, x1, dtype=np.float32)[None, :] - x
            fall = np.exp(-((gx * gx + gy * gy) / (2 * rad * rad)))
            out[y0:y1, x0:x1] += (fall * a * heat)[..., None] * tint
        return out


def render(src, out, profile, dur=6.0, seed=0):
    bgr = cv2.imread(str(src)).astype(np.float32)
    if bgr.shape[:2] != (H, W):
        bgr = cv2.resize(bgr, (W, H), interpolation=cv2.INTER_LANCZOS4)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    depth = depth_proxy(gray)

    # per-profile setup
    if profile == "living":
        keys = [(0.0, 1.00, 0, 0, 0.0), (1.0, 1.075, 26, -12, 0.0)]
        lamp, lsigma, lamp_amt = (540, 250), 430.0, 0.16
        par = 16.0
        dust = Dust(46, (540, 430), 330.0, seed=seed)
        handheld = 0.0
        grain, vign = 2.2, 0.30
    elif profile == "parallax":
        keys = [(0.0, 1.03, -34, 6, -0.25), (1.0, 1.10, 30, -14, 0.20)]
        lamp, lsigma, lamp_amt = (540, 250), 380.0, 0.10
        par = 26.0
        dust = Dust(30, (540, 430), 300.0, seed=seed + 3)
        handheld = 1.6
        grain, vign = 2.6, 0.34
    else:  # comparison - what the current pipeline does (linear zoom, no motion)
        keys = [(0.0, 1.00, 0, 0, 0.0), (1.0, 1.16, 0, 0, 0.0)]
        lamp, lsigma, lamp_amt = (540, 250), 430.0, 0.0
        par = 0.0
        dust = None
        handheld = 0.0
        grain, vign = 0.0, 0.30

    glow = glow_mask(lamp, lsigma) if lamp_amt > 0 else None
    n_frames = int(round(dur * FPS))
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    cx, cy = W / 2.0, H / 2.0
    vig = 1.0 - vign * ((xx - cx) ** 2 / cx ** 2 + (yy - cy) ** 2 / cy ** 2) / 2.0
    vign_map = np.clip(vig, 0, 1)[..., None]

    proc = subprocess.Popen(
        [FF, "-nostdin", "-y", "-hide_banner", "-loglevel", "error",
         "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", str(FPS),
         "-i", "-", "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "19",
         "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)],
        stdin=subprocess.PIPE)

    rng = np.random.default_rng(seed + 11)
    for i in range(n_frames):
        t = i / FPS
        p = i / max(1, n_frames - 1)
        z, px, py, roll = keyframes(keys, p)

        if handheld:
            px += handheld * (math.sin(2 * math.pi * 0.7 * t) + 0.6 * math.sin(2 * math.pi * 1.9 * t + 1.3))
            py += handheld * (math.sin(2 * math.pi * 0.5 * t + 0.7) + 0.5 * math.sin(2 * math.pi * 2.3 * t))

        th = math.radians(roll)
        cos_t, sin_t = math.cos(th), math.sin(th)
        dx, dy = xx - cx - px, yy - cy - py
        rx = cos_t * dx - sin_t * dy
        ry = sin_t * dx + cos_t * dy
        mapx = (cx + rx / z).astype(np.float32)
        mapy = (cy + ry / z).astype(np.float32)

        if par:  # 2.5D: displace by depth so near pixels travel further
            d = cv2.remap(depth, mapx, mapy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
            shift = -par * (d - 0.5) * math.sin(math.pi * p)  # 0 at both ends
            mapx = mapx + shift
            mapy = mapy + shift * 0.35

        frame = cv2.remap(bgr, mapx, mapy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)

        if glow is not None:
            lvl = lamp_level(t, seed)
            add = (lvl - 1.0) * lamp_amt * 255
            frame += (glow * add)[..., None] * np.array([0.42, 0.75, 1.0], dtype=np.float32)
            heat = np.clip((lvl - 0.92) / 0.2, 0, 1)
        else:
            heat = 0.0

        if dust is not None and heat > 0.02:
            frame = dust.draw(frame, t, heat)

        if grain:
            frame += rng.normal(0, grain, (H, W, 1)).astype(np.float32)
        frame *= vign_map
        frame *= 1.0 + 0.004 * math.sin(2 * math.pi * 0.23 * t + 0.3)

        proc.stdin.write(np.clip(frame, 0, 255).astype(np.uint8).tobytes())
        if i % 30 == 0:
            print(f"  {profile}: frame {i}/{n_frames}", flush=True)

    proc.stdin.close()
    if proc.wait():
        raise SystemExit(f"ffmpeg failed for {out}")
    print(f"  wrote {out}", flush=True)


if __name__ == "__main__":
    src, out, profile = sys.argv[1], sys.argv[2], sys.argv[3]
    dur = float(sys.argv[4]) if len(sys.argv) > 4 else 6.0
    render(Path(src), Path(out), profile, dur)
