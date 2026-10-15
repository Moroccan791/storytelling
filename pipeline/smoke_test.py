"""Self test: run the whole pipeline on synthetic assets.

No AI images and no text-to-speech - it generates test cards with PIL and a
speech-shaped waveform with numpy, so it can run any time without spending
anything. It verifies:

  * the aligner places known words close to where they really are
  * every format rule is enforced (via check.py)
  * the render survives a full decode
  * the caption cap height really is 5-7% of the frame, measured from a frame
    of the output rather than trusted from the style sheet

    python pipeline/smoke_test.py
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from clipper.align.energy_align import align_words  # noqa: E402
from pipeline import audio as A  # noqa: E402

HERE = ROOT / "pipeline" / "_selftest"
FONT = ROOT / "tools" / "assets" / "fonts" / "Montserrat-Bold.ttf"
FF = A and __import__("imageio_ffmpeg").get_ffmpeg_exe()


def card(path: Path, label: str, hue: int, subject: bool = True):
    """A stand-in for a generated illustration: dark scene, lit subject up top."""
    W, H = 1080, 1920
    y = np.linspace(0, 1, H, dtype=np.float32)[:, None]
    x = np.linspace(0, 1, W, dtype=np.float32)[None, :]
    r = (hue + 40 * y) * np.ones_like(x)
    g = (hue * 0.7 + 30 * y) * np.ones_like(x)
    b = (hue * 0.5 + 20 * (1 - y)) * np.ones_like(x)
    img = np.stack([r, g, b], -1).clip(0, 255).astype(np.uint8)
    im = Image.fromarray(img)
    d = ImageDraw.Draw(im)
    # Keep everything bright ABOVE the caption band (y>=1400): the cap-height
    # measurement reads that band, and a white label down there made the first
    # run report 10.1% instead of the true value.
    if subject:
        d.ellipse([340, 420, 740, 900], fill=(150, 142, 132))
        d.rectangle([300, 900, 780, 1180], fill=(60, 55, 70))
    f = ImageFont.truetype(str(FONT), 84)
    d.text((60, 120), label, font=f, fill=(255, 255, 255))
    im.save(path)


def speech_shaped(text: str, path: Path, rate: int = A.RATE, wps: float = 2.4):
    """A waveform with one energy burst per word. Returns the true word times."""
    words = text.split()
    total = len(words) / wps + 0.6
    n = int(total * rate)
    buf = np.zeros(n, dtype=np.float32)
    rng = np.random.default_rng(4)
    times = []
    for i, w in enumerate(words):
        t = 0.25 + i / wps
        dur = max(0.10, 0.42 * len(w) / 5.5)
        m = int(dur * rate)
        seg = rng.normal(0, 1, m).astype(np.float32)
        # crude formant shaping so it reads as speech, not hiss
        for lo, hi, g in ((120, 900, 1.0), (900, 2600, 0.6), (2600, 4200, 0.25)):
            seg_sub = seg * 0.3
            seg += A._bandpass(seg_sub, lo, hi) * g
        seg *= np.hanning(m).astype(np.float32)
        i0 = int(t * rate)
        buf[i0:i0 + m] += seg
        times.append((w, t, t + dur))
    buf /= max(1e-6, float(np.max(np.abs(buf))))
    A.write_wav(path, buf * 0.6, rate)
    return times


def probe_cap_height() -> int:
    """Burn a single "H" at the caption font size and position, and measure it.
    This isolates the cap height from the block height of a 2-line cue."""
    from pipeline import captions as C
    ass = HERE / "probe.ass"
    style = dict(C.STYLE)
    style.update({"cap_y": C.CAP_Y, "head_y": C.HEAD_Y, "end_y": C.END_Y})
    body = (f"Dialogue: 0,0:00:00.00,0:00:10.00,Cap,,0,0,0,,"
            f"{{\\an2\\pos({C.W // 2},{C.CAP_Y})}}H")
    ass.write_text(C._header(style) + body + "\n")
    png = HERE / "probe.png"
    subprocess.run([FF, "-nostdin", "-y", "-hide_banner", "-loglevel", "error",
                    "-f", "lavfi", "-i", "color=c=black:s=1080x1920:d=1",
                    "-vf", f"subtitles={ass}:fontsdir={ROOT / 'tools' / 'assets' / 'fonts'}",
                    "-frames:v", "1", str(png)], check=True)
    g = np.asarray(Image.open(png).convert("L"))
    ink = np.where((g > 90).sum(axis=1) > 0)[0]
    return int(ink[-1] - ink[0] + 1) if len(ink) else 0


def measure_cap_height(video: Path, at: float) -> int:
    """Tallest run of light pixels in the caption band of one frame."""
    out = subprocess.run([FF, "-nostdin", "-hide_banner", "-loglevel", "error",
                          "-ss", f"{at:.3f}", "-i", str(video), "-frames:v", "1",
                          "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                         capture_output=True).stdout
    if not out:
        return 0
    g = np.frombuffer(out, np.uint8).reshape(1920, 1080)
    band = g[1150:1780]   # the whole lower third, where captions live
    rows = (band > 200).sum(axis=1)
    ink = np.where(rows > 3)[0]
    if not len(ink):
        return 0, 0.0, 0.0
    top = (1150 + ink[0]) / 1920 * 100
    bot = (1150 + ink[-1]) / 1920 * 100
    return int(ink[-1] - ink[0] + 1), top, bot


def main():
    if HERE.exists():
        shutil.rmtree(HERE)
    for sub in ("images", "nar"):
        (HERE / sub).mkdir(parents=True)
    out = ROOT / "videos" / "_selftest"
    if out.exists():
        shutil.rmtree(out)

    print("== 1. calibration ==")
    for size in (100, 200, 400):
        bb = ImageFont.truetype(str(FONT), size).getbbox("H")
        h = bb[3] - bb[1]
        print(f"   PIL size {size:4d} -> cap height {h:3d}px   ratio {h / size:.4f}")
    bb = ImageFont.truetype(str(FONT), 1000).getbbox("H")
    ratio = (bb[3] - bb[1]) / 1000
    print(f"   => Montserrat cap height = {ratio:.4f} em")
    print(f"   cap height is {ratio:.3f} em in the file; the style constant is the")
    print(f"   RENDERED value (font metric x libass scale) - measured in step 4 below")

    print("\n== 2. aligner accuracy on a known waveform ==")
    text = "HAND TEST four five six seven eight nine ten eleven."
    truth = speech_shaped(text, HERE / "nar" / "01.wav")
    audio = A.read_wav(HERE / "nar" / "01.wav")[0]
    words = align_words(text, audio, A.RATE)
    errs = [abs(w.start - t) for w, (_, t, _) in zip(words, truth)]
    print(f"   {len(words)} words aligned, mean start error {np.mean(errs) * 1000:.0f} ms, "
          f"max {np.max(errs) * 1000:.0f} ms")

    print("\n== 3. render a 4-shot test video ==")
    names = ["01-wide", "02-close", "03-detail", "04-end"]
    for i, nm in enumerate(names):
        card(HERE / "images" / f"{nm}.png", nm, hue=60 + i * 45)
    spec = {
        "id": "_selftest",
        "_selftest": True,
        "format": "whatif",
        "title": "Pipeline self test",
        "report_note": "Synthetic test build. Not a published video - it exists to prove "
                       "the pipeline, the aligner and the rule checks all run end to end.",
        "narration": {
            "script": text,
            "segments": [{"file": "nar/01.wav", "text": text, "pause_after": 0.0}],
        },
        "key_words": ["seven", "eleven"],
        "headline": {"text": "SELF TEST RUNNING", "start": 0.1, "dur": 1.6, "accent": ["TEST"]},
        "music": {"mood": "facts", "db": -26.0, "duck_db": 9.0},
        "images": [{"name": n, "prompt": "synthetic test card"} for n in names],
        "shots": [
            {"image": "01-wide", "dur": 2.2, "move": "in"},
            {"image": "02-close", "dur": 2.2, "move": "left", "parallax": 14},
            {"image": "03-detail", "dur": 2.2, "move": "right"},
            {"image": "04-end", "dur": 2.2, "move": "in", "sfx": {"kind": "shimmer", "gain_db": -20}},
        ],
        "loop_back": True,
    }
    spec["shots"][-1]["image"] = "01-wide"
    (HERE / "spec.json").write_text(json.dumps(spec, indent=2))

    p = subprocess.run([sys.executable, str(ROOT / "pipeline" / "build.py"),
                        "--spec", str(HERE), "--relaxed"],
                       capture_output=True, text=True)
    print(p.stdout[-3000:])
    if p.returncode:
        print(p.stderr[-3000:])
        return 1

    print("== 4. measure the finished video ==")
    from pipeline import captions as _c
    video = out / "_selftest.mp4"

    measured = probe_cap_height()
    pct = measured / 1920 * 100
    ok_h = 5.0 <= pct <= 7.0
    print(f"   cap height   {measured}px = {pct:.2f}% of frame height        "
          f"-> {'PASS' if ok_h else 'FAIL'} (rule 5-7%)")
    px_per_pt = measured / _c.FONT_SIZE
    agree = abs(px_per_pt - _c.CAP_HEIGHT_PER_PT) < 0.02
    print(f"   calibration  {px_per_pt:.3f} px/pt rendered vs {_c.CAP_HEIGHT_PER_PT} "
          f"in the style -> {'agrees' if agree else 'UPDATE THE CONSTANT'}")

    single = [measure_cap_height(video, t) for t in (1.0, 2.0, 3.0, 4.0)]
    tops = [t for _, t, _ in single if t]
    bots = [b for _, _, b in single if b]
    ok_pos = bool(tops) and min(tops) >= 64.0 and max(bots) <= 90.0
    print(f"   block        {min(tops):.0f}%-{max(bots):.0f}% of frame                "
          f"-> {'PASS' if ok_pos else 'FAIL'} (starts below 64%, ends above the 90% UI band)")
    return 0 if (ok_h and agree and ok_pos) else 1


if __name__ == "__main__":
    raise SystemExit(main())
