"""Recover caption-free stills for each illustration from the finished film.

The six source illustrations are not in this repository, and are not in
`Moroccan791/system` either. But every one of them appears in
`post1/the-last-call.mp4`, and captions only cover about two thirds of the
runtime - so for each illustration there is a window where nothing is burnt
over the picture.

This finds, per illustration, a moment inside that illustration's shots with
no caption on screen, and pulls a frame. Useful for:

  * a starting point for motion/ animation when `post1/images/` is gone
  * reference stills for a hosted image-to-video model

These are decoded from the finished H.264, so they are a compressed, already
framed version of the originals - not a substitute for the real source files
if you still have them.

    python motion/extract_stills.py                 # writes motion/src/*.png
    python motion/extract_stills.py --out DIR
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import imageio_ffmpeg

FF = imageio_ffmpeg.get_ffmpeg_exe()
HERE = Path(__file__).resolve().parent
POST = HERE.parent / "post1"


def caption_intervals(post: Path):
    cues = json.loads((post / "captions.json").read_text())
    return sorted((c["start"], c["end"]) for c in cues)


def clear_windows(post: Path, start: float, end: float):
    """Sub-ranges of [start, end] with no caption on screen, longest first."""
    busy = [(s, e) for s, e in caption_intervals(post) if e > start and s < end]
    free, cursor = [], start
    for s, e in busy:
        if s - cursor > 0.02:
            free.append((cursor, min(s, end)))
        cursor = max(cursor, e)
    if end - cursor > 0.02:
        free.append((cursor, end))
    return sorted(free, key=lambda w: w[0] - w[1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(HERE / "src"))
    ap.add_argument("--post", default=str(POST))
    ap.add_argument("--film", default=None)
    args = ap.parse_args()

    post = Path(args.post)
    film = Path(args.film) if args.film else post / "the-last-call.mp4"
    if not film.is_file():
        raise SystemExit(f"no film at {film}")

    shots = json.loads((post / "project.json").read_text())["shots"]
    per_name: dict[str, list[tuple[float, float]]] = {}
    for start, end, name, *_ in shots:
        per_name.setdefault(name, []).append((start, end))

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    print(f"film: {film}\n{'illustration':16s} {'window':>16s}   quality")
    for name, windows in per_name.items():
        best = None
        for start, end in windows:
            if best is None:
                for w in clear_windows(post, start, end):
                    # prefer a window that is comfortably wide
                    if best is None or (w[1] - w[0]) > (best[1] - best[0]):
                        best = w
        if best is None:
            print(f"{name:16s} {'none':>16s}   skipped (every frame has a caption)")
            continue
        start, end = best
        t = start + (end - start) * 0.5
        dest = out / f"{name}.png"
        subprocess.run([FF, "-nostdin", "-y", "-hide_banner", "-loglevel", "error",
                        "-ss", f"{t:.3f}", "-i", str(film), "-frames:v", "1", str(dest)],
                       check=True)
        print(f"{name:16s} {start:6.2f}-{end:6.2f}s   wrote {dest}")
    print(f"\nStills in {out}")


if __name__ == "__main__":
    main()
