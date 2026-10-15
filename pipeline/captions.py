"""Captions, typed headlines and the end card.

Rule set these implement (from the formats spec):
  * 2-4 words per cue, one line
  * cap height 5-7% of frame height  -> font size derived from CAP_HEIGHT_PER_PT
  * one fixed position, lower centre, clear of the bottom UI band
  * accent colour on the cue's key words, karaoke pop on the spoken word
  * headline types on character by character
  * "Follow for more" appears once, only at the very end

Cue grouping is reused from the vendored clipper (`group_words`); the ASS is
written here because clipper's writer only knows about per-word karaoke and
not about key-word accenting.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools" if (ROOT / "tools").is_dir() else ROOT.parent / "tools"
sys.path.insert(0, str(TOOLS))

from clipper.asr.base import Word  # noqa: E402
from clipper.captions.cues import group_words, layout_lines  # noqa: E402

# Rendered geometry, in pixels per point of ASS font size, at PlayResY=1920.
#
# Every value below is measured by burning probes into real frames, NOT taken
# from the font file. Montserrat's cap height is 0.700 em, but libass renders
# one point at 0.643 of that, so an "H" measures 0.450 px per point. Deriving
# it from the font metrics produced captions 40% too small, and a block-top
# position that was 4% of frame height out. smoke_test.py re-measures the cap
# height on every run and fails if the constant has drifted.
CAP_HEIGHT_PER_PT = 0.450      # an "H"
ASCENDER_PER_PT = 0.471        # tallest ink above the baseline ("bdhkl")
DESCENDER_PER_PT = 0.130       # ink below the baseline ("g")
LINE_HEIGHT_PER_PT = 1.000     # libass line pitch is exactly the font size
ANCHOR_GAP_PER_PT = 0.294      # baseline sits this far above the cap_y anchor
LIBASS_SCALE = 0.643           # face pixels per point, used to measure width
BS_C = chr(92)                 # one backslash, spelled out to avoid escaping bugs
FONT_FILE = TOOLS / "assets" / "fonts" / "Montserrat-Bold.ttf"

W, H = 1080, 1920
TARGET_CAP_RATIO = 0.056       # 5.6% of frame height
FONT_SIZE = round(TARGET_CAP_RATIO * H / CAP_HEIGHT_PER_PT / 2) * 2

# Layout: at this cap height roughly 11 characters fit across 1080 px, so a
# 2-4 word cue is set as up to two lines rather than one line that would run
# off both edges. The block is pinned to the lower third.
MAX_CHARS = 11
MAX_LINES = 2
CAP_Y = 1685                                  # bottom of the caption block
HEAD_Y = 300                                  # typed headline block
END_Y = 1120                                  # "Follow for more"

WHITE = "&H00FFFFFF"
ACCENT = "&H0079C8F5"                         # #F5C879 as ASS &HBBGGRR
BLACK = "&H00000000"

STYLE = {
    "font": "Montserrat",
    "font_bold": "Montserrat ExtraBold",
    "font_size": FONT_SIZE,
    "accent": ACCENT,
    "base": WHITE,
    "outline": 4,
    "shadow": 2,
    "max_words": 4,
    "max_chars": MAX_CHARS,
    "max_lines": MAX_LINES,
    "min_duration": 0.30,
    "max_duration": 2.40,
    "gap_break": 0.40,
    "fade_ms": 90,
}


def text_width(text: str, font_size: float | None = None) -> float:
    """Rendered width of a caption line, in pixels, at the output resolution."""
    from PIL import ImageFont
    f = ImageFont.truetype(str(FONT_FILE), 1000)
    bb = f.getbbox(text)
    return (bb[2] - bb[0]) / 1000.0 * (font_size or FONT_SIZE) * LIBASS_SCALE


def cue_lines(ass_text: str, pad: int = 6) -> tuple[int, float]:
    """(max lines in any cue, widest rendered line) parsed back out of the ASS.
    Used by check.py so the layout is verified after the fact, not assumed."""
    import re
    most, widest = 1, 0.0
    for line in ass_text.splitlines():
        if not (line.startswith("Dialogue:") and ",Cap," in line):
            continue
        parts = line.split(",", 9)
        if len(parts) < 10:      # Text is the 10th field of a Dialogue line
            continue
        body = re.sub(r"\{[^}]*\}", "", parts[9])
        rows = body.split("\\N")
        most = max(most, len(rows))
        for r in rows:
            widest = max(widest, text_width(r.strip()))
    return most, widest + 2 * pad


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("{", "(").replace("}", ")").replace("\n", "\\N")


def _hms(t: float) -> str:
    if t < 0:
        t = 0.0
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _header(style: dict) -> str:
    fs = style["font_size"]
    y = style["cap_y"]
    return f"""[Script Info]
; built by pipeline/captions.py
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{style['font']},{fs},{style['base']},{style['accent']},{BLACK},&H64000000,1,0,0,0,100,100,1,0,1,{style['outline']},{style['shadow']},2,60,60,{H - y},1
Style: Head,{style['font_bold']},{int(fs * 1.15)},{style['base']},{style['accent']},{BLACK},&H64000000,1,0,0,0,100,100,1,0,1,5,3,8,60,60,{style['head_y']},1
Style: End,{style['font_bold']},{int(fs * 0.86)},{style['accent']},{style['accent']},{BLACK},&H64000000,1,0,0,0,100,100,1,0,1,4,2,5,60,60,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def word_events(cues, style: dict) -> list[str]:
    """One Dialogue per word: the whole cue stays on screen, the spoken word
    pops, and any word flagged `key` wears the accent colour throughout.

    Multi-line: `layout_lines` splits a cue into up to `max_lines` balanced
    lines, joined here with \\N.
    """
    out = []
    for cue in cues:
        words = cue.words
        lines = layout_lines(words, style["max_chars"], style["max_lines"])
        # which word index ends each line, so we know where to break
        breaks, k = set(), 0
        for line in lines:
            k += len(line)
            breaks.add(k - 1)

        for i, w in enumerate(words):
            start = w.start
            end = words[i + 1].start if i + 1 < len(words) else cue.end
            if end <= start:
                end = start + 0.08
            parts = []
            for j, ww in enumerate(words):
                if j > 0:
                    parts.append("\\N" if (j - 1) in breaks else " ")
                colour = style["accent"] if getattr(ww, "key", False) else style["base"]
                tags = f"\\c{colour}"
                if j == i:
                    tags += "\\fscx106\\fscy106"
                seg = "{" + tags + "}" + _escape(ww.text)
                if j == i:
                    seg += "{\\fscx100\\fscy100}"
                parts.append(seg)
            body = "".join(parts)
            if i == 0:
                body = f"{{\\fad({style['fade_ms']},0)}}" + body
            pos = f"{{\\an2\\pos({W // 2},{style['cap_y']})}}"
            out.append(f"Dialogue: 0,{_hms(start)},{_hms(end)},Cap,,0,0,0,,{pos}{body}")
    return out


def fit_headline(text: str, style: dict, *, max_ratio: float = 0.90,
                 wrap: int = 2) -> tuple[float, list[str]]:
    """Pick a headline size (and line breaks) that fits the frame width.

    A headline is set larger than captions and is centred at the top, so it is
    the one piece of text that can silently run off both edges - the first
    build did exactly that. Size to `max_ratio` of the width instead, wrapping
    to at most `wrap` lines only if a single line cannot be made to fit.
    """
    limit = W * max_ratio
    words = text.split()
    base = style["font_size"] * 1.35

    def width_of(lines: list[str], size: float) -> float:
        return max(text_width(ln, size) for ln in lines)

    # try one line, then two, and take the largest size that fits
    for n_lines in range(1, wrap + 1):
        if n_lines == 1:
            groups = [[text]]
        else:
            if len(words) < 2:
                break
            # split near the middle, biased to the shorter half
            half = max(1, len(words) // 2)
            groups = [[" ".join(words[:half]), " ".join(words[half:])]]
        size = base
        while size > 24 and width_of(groups[0], size) > limit:
            size -= 2
        if width_of(groups[0], size) <= limit:
            return size, groups[0]
    size = 24
    return size, groups[0]


def headline_events(headline: dict, style: dict) -> list[str]:
    """Type the headline on, revealing one character at a time.

    `headline` = {"text": ..., "start": ..., "dur": ..., "accent": ["EARTH"]}
    """
    text = headline["text"]
    start = float(headline["start"])
    dur = float(headline["dur"])
    accent_words = {a.strip(".,!?:;'\"").upper() for a in headline.get("accent", [])}

    # one flag per character: is it inside an accented word?
    flags: list[bool] = []
    for token in text.split(" "):
        flags.extend([token.strip(".,!?:;'\"").upper() in accent_words] * len(token))
        flags.append(False)          # the space we put back below
    flags = flags[: len(text)]

    size, text_lines = fit_headline(text, style)
    step = dur / max(1, len(text))
    out = []
    for k in range(1, len(text) + 1):
        t0 = start + (k - 1) * step
        t1 = start + k * step if k < len(text) else start + dur
        parts, cur = [], None
        for ch, acc in zip(text[:k], flags[:k]):
            want = style["accent"] if acc else style["base"]
            if want != cur:
                # colour tags must live INSIDE an override block, and the
                # text must live outside it
                parts.append("{" + BS_C + "c" + want + "}")
                cur = want
            parts.append(_escape(ch))
        caret = "|" if k < len(text) else ""
        fade = "\\fad(120,0)" if k == 1 else ""
        HEAD_TAG = "\\an8\\pos("
        head = ("{" + HEAD_TAG + f"{W // 2},{style['head_y']}" + ")"
                + BS_C + "fs" + str(int(size)) + fade + "}")
        out.append(f"Dialogue: 0,{_hms(t0)},{_hms(t1)},Head,,0,0,0,,{head}{''.join(parts)}{caret}")
    return out


def end_card(dur: float, style: dict, *, hold: float = 2.6, text: str = "Follow for more") -> list[str]:
    start = max(0.0, dur - hold)
    pos = f"{{\\an5\\pos({W // 2},{style['end_y']})\\fad(320,0)}}"
    return [f"Dialogue: 0,{_hms(start)},{_hms(dur)},End,,0,0,0,,{pos}{_escape(text)}"]


def make(
    words: list[Word],
    out: str | Path,
    *,
    duration: float,
    key_words: set[str] | None = None,
    headline: dict | None = None,
    endcard: dict | None = None,
    style: dict | None = None,
) -> tuple[Path, list]:
    """words -> (.ass path, cues)."""
    st = dict(STYLE)
    if style:
        st.update(style)
    st.setdefault("cap_y", CAP_Y)
    st.setdefault("head_y", HEAD_Y)
    st.setdefault("end_y", END_Y)

    key_words = {k.lower().strip('.,!?…"“”') for k in (key_words or set())}
    if key_words:
        for w in words:
            if w.text.lower().strip('.,!?…"“”') in key_words:
                setattr(w, "key", True)

    cues = group_words(words, max_words=st["max_words"], max_chars=st["max_chars"],
                       max_lines=st.get("max_lines", MAX_LINES),
                       min_duration=st["min_duration"],
                       max_duration=st["max_duration"], gap_break=st["gap_break"])

    events = word_events(cues, st)
    if headline:
        events += headline_events(headline, st)
    if endcard is not False:
        events += end_card(duration, st, **(endcard or {}))

    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_header(st) + "\n".join(events) + "\n")
    return out, cues
