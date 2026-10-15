# tools/ — vendored caption pipeline

A read-only subset of [`Moroccan791/system`](https://github.com/Moroccan791/system), branch `arena/14b1cc76-system`, copied here so a clean clone of this repository can re-render a post.

| | |
| --- | --- |
| Source repository | `Moroccan791/system` |
| Source branch | `arena/14b1cc76-system` |
| Source commit | `f0c5eed5367bf472e47c0aef7ba79052aa59bfee` (2026-10-14) |
| Copied | `clipper/`, `assets/fonts/`, `assets/Montserrat-OFL.txt` |
| Not copied | `assets/broll/`, `assets/icons/`, `assets/models/`, `assets/sfx/` |
| Size | 74 files, ~2.3 MB |

Every copied file is pinned by SHA-256 in [`SOURCE.json`](SOURCE.json), so a re-vendor can be verified byte for byte.

## Why it is here

`post1/prepare.py` and `post1/render.py` import from it directly:

```python
from clipper.ffmpeg import decode_audio
from clipper.asr.moonshine import MoonshineProvider
from clipper.asr.base import Word
from clipper.captions.ass import write_ass
from clipper.captions.cues import group_words
from clipper.config import DEFAULT_STYLE, deep_merge
```

`render.py` also passes `assets/fonts` to ffmpeg as `fontsdir=`, so the Montserrat faces used for the burnt-in captions ship here too, under the SIL Open Font License.

These modules reach **12 files** transitively — `ffmpeg`, `config`, `util/{__init__,log,timecode}`, `align/{energy_align,vad}`, `asr/{base,moonshine}`, `captions/{ass,cues}`. The rest of `clipper/` (ingest, style, select, edit, serve) is unused by Post 1 but is kept intact so this stays a faithful, verifiable subset rather than a hand-trimmed fork.

## Rules

1. **Treat it as read-only.** Fixes belong upstream in `Moroccan791/system`; re-vendor afterwards by re-running the copy and regenerating `SOURCE.json`.
2. **Do not edit to make local scripts pass.** If `post1/` needs a different behaviour, prefer passing arguments from the caller.
3. `PYTHONPATH` does not need to be set. Both scripts resolve this directory themselves — as `tools/` beside the script, or `tools/` at the repository root.

## Dependencies

Only the import paths that Post 1 exercises need to be installed. The heavy optional extras (`opencv-python`, `faster-whisper`, `pywhispercpp`, `rapidocr-onnxruntime`) are not needed and `requirements.txt` does not pull them in.

| Path | Needs |
| --- | --- |
| Captions + render (`render.py`) | `imageio-ffmpeg`, `numpy`, `pillow` |
| Transcription (`prepare.py`) | the above plus `moonshine-cpp`, `onnxruntime`, `silero-vad` |

The wheel for `imageio-ffmpeg` ships a static ffmpeg built `--enable-libass --enable-libfreetype --enable-libx264`, which is what burns the captions in.

## Verified

Re-running the caption stage of `post1/render.py` against the committed `post1/transcript-asr.json` reproduces `words.json`, `captions.json`, `captions.ass` and `style.json` **byte for byte**, and the ASS file burns in correctly with `fontsdir` pointing at `assets/fonts`.
