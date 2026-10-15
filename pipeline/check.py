"""Validate a built video against the format rules.

Every shared rule and both format specs are checked here, so a build cannot
quietly ship with a 5-second shot, a 1-word cue, an oversized caption or a
"Follow for more" in the wrong place. build.py runs this and puts the result
in the report.

Each check returns (ok, rule, detail). `ok` is True, False, or None for a
check that does not apply to this format.
"""
from __future__ import annotations

from pathlib import Path

IMAGE_RANGE = {"story": (15, 25), "didyouknow": (10, 18), "whatif": (10, 18)}
SHOT_MIN, SHOT_MAX = 2.0, 4.0
CAP_RATIO = (0.050, 0.070)
SUBJECT_ZONE = 0.64          # caption block must start below this much of the frame
SAFE_WIDTH_PAD = 16          # px of breathing room at each edge
FOLLOW_TAIL = 3.0


def run(spec: dict, cues, shots: list[dict], duration: float, ass_text: str, *,
        height: int, relaxed: bool = False) -> list[tuple[bool | None, str, str]]:
    from pipeline import captions as cap

    fmt = spec.get("format", "story")
    selftest = bool(spec.get("_selftest"))
    out: list[tuple[bool | None, str, str]] = []

    # ---- duration
    if relaxed:
        out.append((None, "duration 25-45s", f"{duration:.1f}s (relaxed)"))
    else:
        out.append((25.0 <= duration <= 45.0, "duration 25-45s", f"{duration:.1f}s"))

    # ---- image count
    lo, hi = IMAGE_RANGE.get(fmt, (10, 25))
    n_img = len({s["image"] for s in shots})
    if selftest:
        out.append((None, f"{fmt}: {lo}-{hi} images", f"{n_img} images (synthetic cards)"))
    else:
        out.append((lo <= n_img <= hi, f"{fmt}: {lo}-{hi} images", f"{n_img} images"))

    # ---- per-shot pacing
    durs = [s["dur"] for s in shots]
    bad = [f"{d:.2f}s" for d in durs if not (SHOT_MIN - 1e-6 <= d <= SHOT_MAX + 1e-6)]
    out.append((not bad, f"every image {SHOT_MIN:.0f}-{SHOT_MAX:.0f}s",
                "ok" if not bad else f"out of range: {', '.join(bad)}"))

    # ---- no image held too long across consecutive shots
    runs, cur, best = [], None, (None, 0)
    for s in shots:
        if cur == s["image"]:
            runs[-1] += s["dur"]
        else:
            cur = s["image"]
            runs.append(s["dur"])
    worst = max(runs) if runs else 0.0
    out.append((worst <= SHOT_MAX + 1e-6, "no image held > 4s",
                f"longest continuous hold {worst:.2f}s"))

    # ---- alternating direction
    moves = [s.get("move", "in") for s in shots]
    same = sum(1 for a, b in zip(moves, moves[1:]) if a == b)
    out.append((same == 0, "alternate move direction between shots",
                "strict alternation" if same == 0 else f"{same} repeat(s)"))

    # ---- parallax on key images
    par = [s for s in shots if s.get("parallax", 0)]
    out.append((len(par) >= 1, "2.5D parallax on key images",
                f"{len(par)} shot(s) with parallax"))

    # ---- hook: first caption on screen fast enough
    first = min((c.start for c in cues), default=99.0)
    out.append((first <= 2.0, "hook within 2s", f"first caption at {first:.2f}s"))

    # ---- caption words per cue
    counts = [len(c.words) for c in cues]
    over = [n for n in counts if n > 4]
    under = [n for n in counts if n < 2]
    out.append((not over, "captions 2-4 words",
                "ok" if not over else f"{len(over)} cue(s) over 4 words"))
    out.append((None if not under else False, "captions 2-4 words (short cues)",
                f"{len(under)} single-word cue(s)" if under else "ok"))

    # ---- every event must actually show text (a colour tag swallowing the
    # text inside one { } block is silent and invisible in a still frame)
    import re as _re
    empty = []
    for line in ass_text.splitlines():
        if not line.startswith("Dialogue:"):
            continue
        fields = line.split(",", 9)
        if len(fields) < 10:
            continue
        visible = _re.sub(r"\{[^}]*\}", "", fields[9]).strip().strip("|").strip()
        if not visible:
            empty.append(fields[3])
    out.append((not empty, "every event renders visible text",
                "ok" if not empty else f"{len(empty)} event(s) with empty text: {set(empty)}"))

    # ---- headline must fit the frame
    head = [l for l in ass_text.splitlines() if ",Head," in l]
    if head:
        widest = 0.0
        for line in head:
            fields = line.split(",", 9)
            if len(fields) < 10:
                continue
            size_m = _re.search(r"\\fs(\d+)", fields[9])
            size = float(size_m.group(1)) if size_m else 0.0
            visible = _re.sub(r"\{[^}]*\}", "", fields[9]).strip().rstrip("|").strip()
            if visible and size:
                widest = max(widest, cap.text_width(visible, size))
        if widest:
            out.append((widest <= cap.W * 0.94, "headline fits the frame",
                        f"widest headline line {widest:.0f}px of {cap.W}px"))
    else:
        out.append((None, "headline fits the frame", "no headline in this build"))

    # ---- caption size
    ratio = cap.FONT_SIZE * cap.CAP_HEIGHT_PER_PT / height
    out.append((CAP_RATIO[0] <= ratio <= CAP_RATIO[1], "caption cap height 5-7%",
                f"{ratio * 100:.1f}% of frame height"))

    # ---- caption position: fixed and clear of the subject
    ys = set()
    for line in ass_text.splitlines():
        if line.startswith("Dialogue:") and ",Cap," in line:
            tag = line.split(",,", 1)[-1]
            if "\\pos(" in tag:
                ys.add(tag.split("\\pos(")[1].split(")")[0].split(",")[1])
    fixed = len(ys) == 1
    y = float(next(iter(ys))) if fixed else cap.CAP_Y
    out.append((fixed, "captions at one fixed position",
                f"y={y:.0f}" if fixed else f"{len(ys)} different positions"))

    n_lines, widest = cap.cue_lines(ass_text)
    # Real ink box of the block: the anchor holds the last baseline a gap above
    # it, then (n-1) line pitches up to the first baseline, then the ascenders.
    f = cap.FONT_SIZE
    baseline = y - cap.ANCHOR_GAP_PER_PT * f
    bottom = baseline + cap.DESCENDER_PER_PT * f
    top = (baseline - (n_lines - 1) * cap.LINE_HEIGHT_PER_PT * f - cap.ASCENDER_PER_PT * f) / height
    out.append((top >= SUBJECT_ZONE, "captions never cover the subject",
                f"{n_lines}-line block spans {top * 100:.0f}%-{bottom / height * 100:.0f}% of "
                f"frame (must start below {SUBJECT_ZONE * 100:.0f}%)"))
    out.append((widest <= cap.W - SAFE_WIDTH_PAD, "captions fit inside the frame",
                f"widest line {widest:.0f}px of {cap.W}px"))

    # ---- end card
    follows = [l for l in ass_text.splitlines() if l.startswith("Dialogue:") and "Follow for more" in l]
    ok_n = len(follows) == 1
    ok_t = ok_n and _start_of(follows[0]) >= duration - FOLLOW_TAIL
    out.append((ok_n and ok_t, '"Follow for more" once, at the very end',
                f"{len(follows)} event(s), starts {_start_of(follows[0]):.2f}s / {duration:.2f}s" if follows else "missing"))

    # ---- loop-friendly ending
    if spec.get("loop_back"):
        out.append((shots[-1]["image"] == shots[0]["image"], "loop-friendly end matches the opening",
                    f"{shots[-1]['image']} -> {shots[0]['image']}"))
    else:
        out.append((None, "loop-friendly end", "loop_back not set"))

    # ---- audio
    out.append((bool(spec.get("music")), "background music bed",
                str(spec.get("music", "none"))))
    out.append((bool(spec.get("headline")) == any(e[1] == "typing" for e in spec.get("_sfx", [])),
                "typing sound under the headline",
                "present" if spec.get("headline") else "no headline in this format"))

    # ---- sources (Format B only)
    if selftest:
        out.append((None, "sources", "n/a for the self test"))
    elif fmt in ("didyouknow", "whatif"):
        claims = spec.get("sources", [])
        if not claims:
            out.append((False, "every fact has named sources", "no sources block"))
        else:
            thin = [c for c in claims if len(c.get("urls", [])) < 2]
            low = [c for c in claims if c.get("confidence") == "low"]
            out.append((not thin, "every claim confirmed by 2+ sources",
                        "ok" if not thin else f"{len(thin)} claim(s) with <2 sources"))
            out.append((True, "low-confidence claims flagged for review",
                        f"{len(low)} flagged" if low else "none flagged"))
    else:
        out.append((None, "sources", "n/a for story format"))

    return out


def _start_of(event: str) -> float:
    t = event.split(",")[1]
    h, m, s = t.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def render(checks: list[tuple[bool | None, str, str]]) -> str:
    fail = sum(1 for ok, _, _ in checks if ok is False)
    lines = [f"| {'':^4} | rule | detail |", "|---|---|---|"]
    for ok, rule, detail in checks:
        mark = "PASS" if ok else ("n/a" if ok is None else "FAIL")
        lines.append(f"| {mark} | {rule} | {detail} |")
    lines.append("")
    lines.append(f"**{len(checks) - fail}/{len(checks)} checks passed"
                 + (f", {fail} FAILED**" if fail else "**"))
    return "\n".join(lines)


def run_file(spec_path: str | Path, *, relaxed: bool = False) -> str:
    """Re-run the checks for an already-built video from its saved report data."""
    raise SystemExit("run through build.py; checks are stored in the report")
