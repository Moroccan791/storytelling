"""Assemble generated clips into the finished film.

Same shot plan, captions and narration as `render.py`, but each shot comes from
a real moving clip (Kling, Veo, Wan, LTX-Video, or anything else) instead of a
slow zoom on a still.

    python render_video.py                    # clips from ./clips
    python render_video.py --clips-dir DIR
    python render_video.py --out NAME.mp4

Clips are matched to the shot plan in `project.json` by name:
`01-call.mp4` covers every framing that uses `01-call`. Where one illustration
is used for several shots, each shot takes a different slice of the clip so the
repeated framings do not play the same frames twice.

If a clip is missing, that shot falls back to the still (with the original zoom)
so a half-generated episode still renders.

Clip sound is discarded - the narration and its captions keep their timing.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import imageio_ffmpeg

ROOT = Path(__file__).resolve().parent
TOOLS = ROOT / "tools" if (ROOT / "tools").is_dir() else ROOT.parent / "tools"
sys.path.insert(0, str(TOOLS))

from clipper.config import DEFAULT_STYLE  # noqa: E402  (kept for parity with render.py)

FF = imageio_ffmpeg.get_ffmpeg_exe()
WORK = ROOT / "work" / "video"
FPS = 30
W, H = 1080, 1920
CLIP_EXT = (".mp4", ".mov", ".mkv", ".webm")
MIN_SPEED = 0.65          # never slow a clip below this to fill a shot
DUR_RE = re.compile(r"Duration:\s*(\d+):(\d\d):(\d\d(?:\.\d+)?)")


def run(args, **kw):
    p = subprocess.run([FF, "-nostdin", "-y", "-hide_banner", "-loglevel", "error", *args],
                       capture_output=True, text=True, **kw)
    if p.returncode:
        raise RuntimeError(f"ffmpeg failed:\n{' '.join(map(str, args))}\n{p.stderr[-3000:]}")
    return p.stdout


def probe_duration(path: Path) -> float:
    """ffmpeg ships without ffprobe here, so read Duration off the banner."""
    p = subprocess.run([FF, "-hide_banner", "-i", str(path)], capture_output=True, text=True)
    m = DUR_RE.search(p.stderr)
    if not m:
        raise RuntimeError(f"cannot read duration of {path}")
    h, mnt, s = m.groups()
    return int(h) * 3600 + int(mnt) * 60 + float(s)


def find_clip(clips_dir: Path, name: str):
    for ext in CLIP_EXT:
        for candidate in (clips_dir / f"{name}{ext}", clips_dir / f"{name}.{ext.lstrip('.')}"):
            if candidate.is_file():
                return candidate
    return None


def still_for(name: str, motion_src: Path | None):
    for d in [ROOT / "images", motion_src] if motion_src else [ROOT / "images"]:
        if d and (d / f"{name}.png").is_file():
            return d / f"{name}.png"
    return None


def fit_filter():
    """Fill 1080x1920 without distorting; crop the overflow."""
    return f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},setsar=1"


def build_shot_from_clip(clip: Path, clip_len: float, offset: float, dur: float,
                         out: Path, index: int, indent: str):
    """One shot from one clip. Returns (path, how)."""
    avail = max(0.05, clip_len - offset)

    if avail >= dur:                                    # simple trim
        args = ["-ss", f"{offset:.3f}", "-i", str(clip), "-t", f"{dur:.3f}",
                "-vf", fit_filter(), "-an"]
        how = "trim"
    elif clip_len / dur >= MIN_SPEED:                   # slow it down a little
        speed = clip_len / dur                          # >1 stretches time
        args = ["-i", str(clip), "-t", f"{dur:.3f}",
                "-vf", f"setpts=PTS*{speed:.5f},{fit_filter()}", "-an"]
        how = f"slow {1/speed:.2f}x"
    else:                                               # ping-pong so the loop has no jump
        ping = out.parent / f"_pingpong-{clip.stem}.mp4"
        if not ping.exists():
            run(["-i", str(clip), "-filter_complex",
                 "[0:v]split[a][b];[b]reverse[r];[a][r]concat=n=2:v=1:a=0[v]",
                 "-map", "[v]", "-an", "-c:v", "libx264", "-preset", "veryfast",
                 "-crf", "18", "-pix_fmt", "yuv420p", str(ping)])
        loops = int(dur / (2 * clip_len)) + 2
        args = ["-stream_loop", str(loops), "-i", str(ping), "-t", f"{dur:.3f}",
                "-vf", fit_filter(), "-an"]
        how = "ping-pong"

    run([*args, "-frames:v", str(round(dur * FPS)), "-c:v", "libx264", "-preset", "fast",
         "-crf", "19", "-pix_fmt", "yuv420p", str(out)])
    return out, how


def build_shot_from_still(still: Path, z0: float, z1: float, dur: float, out: Path):
    n = max(1, round(dur * FPS))
    zoom = f"{z0}+({z1 - z0})*on/{max(1, n - 1)}"
    vf = (f"scale={int(W*1.33)}:-2,crop={W}:{H},"
          f"zoompan=z='{zoom}':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d={n}:s={W}x{H}:fps={FPS},setsar=1")
    run(["-loop", "1", "-i", str(still), "-vf", vf, "-frames:v", str(n), "-an",
         "-c:v", "libx264", "-preset", "fast", "-crf", "19", "-pix_fmt", "yuv420p", str(out)])
    return out, "still (fallback)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clips-dir", default=str(ROOT / "clips"))
    ap.add_argument("--motion-src", default=str(ROOT.parent / "motion" / "src"),
                    help="fallback stills if images/ is absent")
    ap.add_argument("--out", default=str(ROOT / "the-last-call-animated.mp4"))
    ap.add_argument("--keep-work", action="store_true")
    args = ap.parse_args()

    clips_dir, motion_src = Path(args.clips_dir), Path(args.motion_src)
    manifest = json.loads((ROOT / "project.json").read_text())
    shots = manifest["shots"]
    total = float(manifest["duration_seconds"])
    WORK.mkdir(parents=True, exist_ok=True)

    lens = {}
    for shot in shots:
        name = shot[2]
        if name not in lens:
            clip = find_clip(clips_dir, name)
            lens[name] = (clip, probe_duration(clip) if clip else None)

    # Spread reused clips across shots so repeated framings differ.
    seen: dict[str, int] = {}
    segments = []
    print(f"{len(shots)} shots, {len(lens)} illustrations, clips from {clips_dir}")
    for i, (start, end, name, z0, z1) in enumerate(shots):
        dur = end - start
        clip, clip_len = lens[name]
        out = WORK / f"shot-{i:02d}.mp4"
        indent = f"  [{i+1:2d}/{len(shots)}] {name:14s} {dur:4.1f}s"
        if clip:
            nth = seen.get(name, 0)
            seen[name] = nth + 1
            # Slide the in-point along the clip for each reuse, keeping it valid.
            spread = max(0.0, clip_len - dur)
            offset = (spread * nth / 1.6) % max(spread, 0.001) if spread else 0.0
            _, how = build_shot_from_clip(clip, clip_len, offset, dur, out, i, indent)
        else:
            still = still_for(name, motion_src)
            if still is None:
                print(f"{indent}  SKIPPED - no clip and no still")
                continue
            _, how = build_shot_from_still(still, z0, z1, dur, out)
        segments.append(out)
        print(f"{indent}  -> {how}")

    if not segments:
        raise SystemExit("nothing to render: no clips and no stills found")

    listing = WORK / "concat.txt"
    listing.write_text("".join(f"file '{p.as_posix()}'\n" for p in segments))
    run(["-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(WORK / "picture.mp4")])

    print("Burning captions and mastering narration...", flush=True)
    captions = ROOT / "captions.ass"
    vf = f"subtitles={captions}:fontsdir={TOOLS/'assets/fonts'},fade=t=out:st={total-0.4:.2f}:d=0.4"
    run(["-i", str(WORK / "picture.mp4"), "-i", str(ROOT / "narration.mp3"), "-vf", vf,
         "-af", "loudnorm=I=-16:TP=-1.5:LRA=9,apad", "-map", "0:v:0", "-map", "1:a:0",
         "-t", f"{total:.3f}", "-c:v", "libx264", "-preset", "fast", "-crf", "19",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
         "-movflags", "+faststart", args.out])

    # Decode the whole file: fail rather than hand over a corrupt render.
    run(["-i", args.out, "-f", "null", "-"])
    if not args.keep_work:
        for f in WORK.glob("shot-*.mp4"):
            f.unlink()
    print("Done:", args.out)


if __name__ == "__main__":
    main()
