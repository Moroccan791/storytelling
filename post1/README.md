# Post 1 — The Last Call

A fictional English mystery with an emotional payoff. Saved in this standalone repository, separate from the `mozillaedit` and `system` repositories. Nothing was added to or changed in the GitHub `system` repository.

Post 1 of this repository; all files for it live in this folder. Posting copy starts in [post.md](post.md).

## Posting details

See [post.md](post.md) for the title, short description, hashtags, and ready-to-copy caption. Machine-readable metadata is in [post.json](post.json).

**[Download the finished MP4](the-last-call.mp4)** · [Read the script](script.txt)

## Deliverables

- `the-last-call.mp4` — 53-second vertical 1080×1920 / 30 fps first cut, H.264 + AAC.
- `narration.mp3` — original generated English voiceover, selected voice `voice-00`.
- `script.txt` — approved production script.
- `images/` — six AI-generated scene illustrations. **Not present in this repository** (see Known gaps).
- `captions.ass`, `captions.json`, `words.json` — subtitles and timing data.
- `project.json` — shot plan and production metadata.

## Known gaps

One thing the pipeline references is not committed here:

- `images/` — the six source scene illustrations (`01-call`, `02-phone`, `03-recording`, `04-door`, `05-table`, `06-stay`). The finished MP4 is unaffected, but `render.py` needs them to re-render and will now exit with a clear message instead of a traceback. They are not present in `Moroccan791/system` either, so they only exist locally.

The caption pipeline is committed: `tools/` at the repository root holds the `clipper/` subset and Montserrat fonts, pinned in `tools/SOURCE.json`. See [`tools/README.md`](../tools/README.md).

## Creative direction

Immediate hook: a son receives a call three days after his father's funeral. The scheduled-recording reveal resolves the supernatural question while opening an emotional one: what is his mother hiding? A dinner table set for two pays it off visually. The son stays rather than delivering an explanatory moral or an engagement-bait call to action.

The original audio runs approximately 52.2 seconds. The film runs 53 seconds, allowing a short closing hold. Six illustrations are cut into eleven framings with restrained slow zooms; no animated character motion or lip sync is claimed. No music is included.

## Caption reuse

`tools/clipper/` is a read-only local subset copied from `Moroccan791/system`, branch `arena/14b1cc76-system`. The source commit is pinned in `tools/SOURCE.json`. Existing Moonshine transcription, energy alignment, cue grouping and ASS rendering are reused rather than rebuilding the caption system. Font assets and their license are included locally. Details in [`tools/README.md`](../tools/README.md).

Caption text is corrected to the known narration script: 117 of the 120 words keep their measured ASR timings, and only 3 (`a`, `Mum`, `Mum…`) fall back to interpolated `script-corrected/approximate` timings. Word timings are energy-aligned approximations, not native forced-alignment timestamps; they should receive a human playback review before publication. This is a first cut, not an empirically tested retention result.

Caption text is corrected to the known narration script. Word timings are energy-aligned approximations, not native forced-alignment timestamps; they should receive a human playback review before publication. This is a first cut, not an empirically tested retention result.

## Re-render

Python dependencies: `imageio-ffmpeg`, `pillow`, `numpy`, `moonshine-cpp` (the latter only for preparing a new transcript; see `requirements.txt`, which leaves the heavy ASR extras commented out).

```bash
python -m venv .venv
# Activate .venv using the command for your operating system.
# macOS / Linux:
source .venv/bin/activate
python -m pip install -r requirements.txt
python prepare.py   # optional - only to regenerate transcript-asr.json
python render.py
```

`render.py` reuses the saved transcript, makes captions and renders the film. FFmpeg comes from the imageio wheel and includes libass. Final validation decodes the full MP4 to check for media errors. Intermediate video segments are in `work/` and need not be published or committed.

`PYTHONPATH` does not need to be set — both scripts locate `tools/` themselves, whether it sits beside the script or at the repository root.

### What the re-render covers

`render.py` reads `narration.mp3` and `transcript-asr.json` and writes `words.json`, `captions.ass`, `captions.json`, `style.json`, `project.json`, `the-last-call.mp4` and `preview.jpg`. Re-running the caption stage against the committed transcript reproduces `words.json`, `captions.ass`, `captions.json` and `style.json` byte for byte.

It still needs `images/` for the picture, which is not in this repository.

## Watch locally

```bash
cd post1
python -m http.server 8080
```

Open `http://localhost:8080` in your own browser. The player includes a download button. GitHub itself may offer the MP4 as a download rather than an inline video.
