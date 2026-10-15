"""Build one video from a spec folder.

    python pipeline/build.py --spec pipeline/specs/<id>

Spec layout (see specs/_template/):

    specs/<id>/spec.json      the video: script, shots, images, sources
    specs/<id>/images/*.png    the generated artwork, 1080x1920
    specs/<id>/nar/*.wav       narration segments in speaking order

Output:

    videos/<id>/<id>.mp4      1080x1920 30fps, captions burned in
    videos/<id>/captions.ass  the caption file that was burned
    videos/<id>/words.json    word-level timings
    videos/<id>/script.txt    the final spoken script
    videos/<id>/sources.md    Format B only
    videos/<id>/report.md     what it did + every rule check

    python pipeline/build.py --spec ... --dry-run     checks only, no render
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(TOOLS))

import numpy as np  # noqa: E402
from clipper.align.energy_align import align_words  # noqa: E402
from clipper.ffmpeg import decode_audio, write_wav  # noqa: E402

from pipeline import audio as A  # noqa: E402
from pipeline import captions as C  # noqa: E402
from pipeline import check as K  # noqa: E402
from pipeline import camera as M  # noqa: E402

FF = M.FF
SR = A.RATE


def sh(args, **kw):
    p = subprocess.run([FF, "-nostdin", "-y", "-hide_banner", "-loglevel", "error", *args],
                       capture_output=True, text=True, **kw)
    if p.returncode:
        raise RuntimeError(f"ffmpeg failed:\n{' '.join(map(str, args))}\n{p.stderr[-3000:]}")
    return p.stdout


# ------------------------------------------------------------------ narration

def assemble_narration(spec: dict, specdir: Path, work: Path) -> tuple[str, Path]:
    """Join the narration segments with their pauses. Returns (script, wav)."""
    nar = spec["narration"]
    out = work / "narration.wav"

    if nar.get("file"):
        src = specdir / nar["file"]
        x, rate = A.read_wav(src) if src.suffix == ".wav" else (decode_audio(src, rate=SR), SR)
        if rate != SR:
            x = np.interp(np.linspace(0, len(x), int(len(x) * SR / rate)),
                          np.arange(len(x)), x).astype(np.float32)
        write_wav(out, x, SR)
        return nar["script"], out

    segs = nar["segments"]
    if not segs:
        raise SystemExit("spec.narration needs either `file` or `segments`")
    pieces, texts = [], []
    for seg in segs:
        src = specdir / seg["file"]
        x, rate = A.read_wav(src) if src.suffix == ".wav" else (decode_audio(src, rate=SR), SR)
        if rate != SR:
            x = np.interp(np.linspace(0, len(x), int(len(x) * SR / rate)),
                          np.arange(len(x)), x).astype(np.float32)
        pieces.append(x)
        pieces.append(np.zeros(int(seg.get("pause_after", 0.25) * SR), dtype=np.float32))
        texts.append(seg["text"].strip())
    joined = np.concatenate(pieces).astype(np.float32)
    write_wav(out, joined, SR)

    script = " ".join(texts)
    if nar.get("script"):
        a = " ".join(nar["script"].split())
        if " ".join(script.split()) != a:
            print("  note: assembled segment text differs from narration.script; using segments")
    return script, out


# ------------------------------------------------------------------ audio plan

def plan_sfx(spec: dict, shots: list[dict]) -> list[tuple[float, str, float]]:
    """Whoosh on every cut (quiet), typing under a headline, plus anything the
    spec asks for explicitly."""
    events: list[tuple[float, str, float]] = []
    t = 0.0
    for i, s in enumerate(shots):
        if i > 0:
            events.append((round(t, 3), "whoosh", s.get("whoosh_db", -27.0)))
        if s.get("sfx"):
            fx = s["sfx"]
            events.append((round(t + fx.get("at", 0.0), 3), fx["kind"], fx.get("gain_db", -20.0)))
        t += s["dur"]

    head = spec.get("headline")
    if head:
        n_clicks = max(1, int(head["dur"] / 0.055))
        for k in range(n_clicks):
            events.append((round(head["start"] + k * 0.055, 3), "typing",
                           head.get("typing_db", -30.0)))
    for e in spec.get("sfx", []):
        events.append((float(e["t"]), e["kind"], float(e.get("gain_db", -20.0))))

    events.sort(key=lambda e: e[0])
    spec["_sfx"] = [[t, k, g] for t, k, g in events]
    return events


# ------------------------------------------------------------------ main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True, help="spec folder or spec.json")
    ap.add_argument("--out", default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--relaxed", action="store_true",
                    help="skip the 25-45s rule (used by the self test)")
    args = ap.parse_args()

    spec_path = Path(args.spec)
    specdir = spec_path if spec_path.is_dir() else spec_path.parent
    spec = json.loads((specdir / "spec.json").read_text())
    vid = spec["id"]
    out = Path(args.out) if args.out else ROOT / "videos" / vid
    work = out / "work"
    work.mkdir(parents=True, exist_ok=True)

    shots = spec["shots"]
    duration = round(sum(s["dur"] for s in shots), 3)
    images_dir = specdir / spec.get("images_dir", "images")

    print(f"building {vid}  ({spec.get('format')}, {len(shots)} shots, {duration:.1f}s)")

    # ---- narration -> words -> captions
    if args.dry_run:
        script = spec["narration"].get("script", " ".join(s["text"] for s in spec["narration"].get("segments", [])))
        words, cues, ass = [], [], ""
    else:
        script, nar_wav = assemble_narration(spec, specdir, work)
        audio16 = decode_audio(nar_wav, rate=16000)
        words = align_words(script, audio16, 16000)
        if not words:
            raise SystemExit("alignment produced no words - is the narration audible?")
        print(f"  aligned {len(words)} words, speech ends at {words[-1].end:.2f}s")

        ass_path, cues = C.make(
            words, work / "captions.ass", duration=duration,
            key_words=set(spec.get("key_words", [])),
            headline=spec.get("headline"),
            endcard=spec.get("endcard") if spec.get("endcard") is not False else False,
        )
        ass = ass_path.read_text()
        (out / "words.json").write_text(json.dumps([w.to_dict() for w in words], indent=2))
        shutil.copy(ass_path, out / "captions.ass")
        (out / "script.txt").write_text(script + "\n")
        print(f"  {len(cues)} cues")

    # ---- sound effects, planned up front so check.py can see them
    events = plan_sfx(spec, shots)

    # ---- checks (before spending render time)
    checks = K.run(spec, cues, shots, duration, ass, height=C.H, relaxed=args.relaxed)
    fails = [c for c in checks if c[0] is False]
    print(K.render(checks).splitlines()[-1])
    for _, rule, detail in fails:
        print(f"  FAIL  {rule}: {detail}")
    if args.dry_run:
        print("\n" + K.render(checks))
        return 1 if fails else 0

    # ---- shots
    t0 = time.time()
    segments = []
    for i, s in enumerate(shots):
        img = images_dir / f"{s['image']}.png"
        if not img.is_file():
            raise SystemExit(f"missing image {img}")
        seg = work / f"shot-{i:02d}.mp4"
        M.render_shot(img, seg, s["dur"], move=s.get("move", "in"),
                      parallax=s.get("parallax", 0.0), grain=s.get("grain", 2.0),
                      vignette=s.get("vignette", 0.32), dust=s.get("dust", 0), seed=i * 5 + 1)
        segments.append(seg)
        print(f"  shot {i + 1:2d}/{len(shots)} {s['image']:18s} {s['dur']:.1f}s {s.get('move', 'in'):5s} "
              f"[{time.time() - t0:5.1f}s]", flush=True)

    listing = work / "concat.txt"
    listing.write_text("".join(f"file '{p.as_posix()}'\n" for p in segments))
    sh(["-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(work / "picture.mp4")])

    # ---- audio
    voice, _ = A.read_wav(work / "narration.wav")
    music = A.music_bed(duration, mood=spec.get("music", {}).get("mood", "story"),
                        seed=abs(hash(vid)) % 1000)
    mix = A.mix(duration, voice, music,
                music_db=spec.get("music", {}).get("db", -26.0),
                duck_db=spec.get("music", {}).get("duck_db", 9.0),
                events=events)
    A.write_wav(work / "mix.wav", mix, SR)
    print(f"  audio: {len(events)} sfx events, music '{spec.get('music', {}).get('mood', 'story')}'")

    # ---- final
    final = out / f"{vid}.mp4"
    vf = (f"subtitles={work / 'captions.ass'}:fontsdir={TOOLS / 'assets' / 'fonts'},"
          f"fade=t=out:st={max(0.0, duration - 0.5):.2f}:d=0.5")
    sh(["-i", str(work / "picture.mp4"), "-i", str(work / "mix.wav"), "-vf", vf,
        "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-map", "0:v:0", "-map", "1:a:0",
        "-t", f"{duration:.3f}", "-c:v", "libx264", "-preset", "fast", "-crf", "19",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        "-movflags", "+faststart", str(final)])
    sh(["-i", str(final), "-f", "null", "-"])          # decode the whole file
    print(f"  wrote {final} ({final.stat().st_size / 1e6:.1f} MB)")

    # ---- sources + report
    write_sources(spec, out)
    write_report(spec, out, duration, shots, cues, checks, events, final)
    print(f"\ndone in {time.time() - t0:.0f}s -> {out}")
    return 0


def write_sources(spec: dict, out: Path):
    src = spec.get("sources") or []
    if not src:
        return
    lines = [f"# Sources — {spec['title']}", "",
             "Every claim below must be backed by two independent sources before it is used.",
             "Claims marked **low confidence** need a human decision before publishing.", ""]
    for i, c in enumerate(src, 1):
        conf = c.get("confidence", "high")
        flag = "  ⚠️ **LOW CONFIDENCE — review**" if conf == "low" else ""
        lines.append(f"## {i}. {c['claim']}{flag}")
        if c.get("note"):
            lines.append(f"_{c['note']}_")
        lines.append("")
        for u in c.get("urls", []):
            lines.append(f"- {u}")
        lines.append("")
    (out / "sources.md").write_text("\n".join(lines))


def write_report(spec, out, duration, shots, cues, checks, events, final):
    durs = [s["dur"] for s in shots]
    imgs = {s["image"] for s in shots}
    lines = [
        f"# Report — {spec['title']}", "",
        f"`{spec['id']}` · format **{spec.get('format')}** · {duration:.2f}s · "
        f"{final.stat().st_size / 1e6:.1f} MB · 1080x1920 @ 30 fps", "",
        "## What it did", "",
        spec.get("report_note",
                 f"{len(imgs)} images cut into {len(shots)} shots over {duration:.1f} seconds."), "",
        "## Shape", "",
        f"| | |", "|---|---|",
        f"| images | {len(imgs)} |",
        f"| shots | {len(shots)} |",
        f"| shot length | min {min(durs):.2f}s · mean {sum(durs) / len(durs):.2f}s · max {max(durs):.2f}s |",
        f"| captions | {len(cues)} cues · max {max((len(c.words) for c in cues), default=0)} words |",
        f"| caption size | {C.FONT_SIZE * C.CAP_HEIGHT_PER_PT / C.H * 100:.1f}% of frame height |",
        f"| sound effects | {len(events)} |",
        f"| music | {spec.get('music', {}).get('mood', 'story')} bed at {spec.get('music', {}).get('db', -26.0)} dB, "
        f"ducked {spec.get('music', {}).get('duck_db', 9.0)} dB under the voice |",
        "",
        "## Rule checks", "",
        K.render(checks), "",
        "## Files", "",
        f"- `{final.name}` — the video",
        "- `script.txt` — the spoken script",
        "- `captions.ass` — burned-in captions",
        "- `words.json` — word-level timings used for the captions",
    ]
    if spec.get("sources"):
        lines.append("- `sources.md` — the facts and where they come from")
    if spec.get("image_prompts"):
        lines.append("- `image-prompts.md` (in the spec folder) — the prompts behind each image")
    (out / "report.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
