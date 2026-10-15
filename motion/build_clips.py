"""Animate every illustration in a post, on CPU, straight from project.json.

Renders one clip per illustration, long enough for the longest shot that uses
it, into the post's `clips/` folder - the exact layout `post1/render_video.py`
expects. Shots that reuse an illustration take different slices of the clip.

    python motion/build_clips.py                      # post1, profile "living"
    python motion/build_clips.py --post post1 --profile parallax
    python motion/build_clips.py --only 05-table

Then build the film:

    cd post1 && python render_video.py --clips-dir clips
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

spec = importlib.util.spec_from_file_location("motion_impl", HERE / "motion.py")
motion = importlib.util.module_from_spec(spec)
spec.loader.exec_module(motion)  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--post", default=str(HERE.parent / "post1"))
    ap.add_argument("--src", default=str(HERE / "src"))
    ap.add_argument("--profile", default="living", choices=["living", "parallax"])
    ap.add_argument("--only", default=None, help="render a single illustration by name")
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    post = Path(args.post)
    src = Path(args.src)
    clips = post / "clips"
    clips.mkdir(parents=True, exist_ok=True)

    shots = json.loads((post / "project.json").read_text())["shots"]
    longest: dict[str, float] = {}
    for start, end, name, *_ in shots:
        longest[name] = max(longest.get(name, 0.0), end - start)

    # "living" keeps faces intact; "parallax" has more depth but can warp them.
    names = [args.only] if args.only else sorted(longest)
    print(f"profile={args.profile}  -> {clips}")
    for i, name in enumerate(names):
        still = src / f"{name}.png"
        if not still.is_file():
            print(f"  {name:16s} SKIPPED - no still at {still}")
            continue
        dest = clips / f"{name}.mp4"
        if dest.exists() and not args.overwrite:
            print(f"  {name:16s} exists, skipping")
            continue
        dur = longest.get(name, 6.0)
        print(f"  {name:16s} {dur:4.1f}s", flush=True)
        motion.render(still, dest, args.profile, dur=dur, seed=i * 7 + 3)
    print(f"\nNow: cd {post.name} && python render_video.py --clips-dir clips")


if __name__ == "__main__":
    main()
