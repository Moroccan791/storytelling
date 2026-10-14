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

Two things the pipeline references are not committed here, so a full re-render cannot run from a clean clone yet:

1. `tools/clipper/` (and its `assets/fonts/`, pinned by `tools/SOURCE.json`) — the shared caption pipeline copied from `Moroccan791/system`. `prepare.py` and `render.py` both insert `tools/` on `sys.path` and fall back to the repository root when this folder is nested one level down, so the scripts work as soon as `tools/` is restored at the repository root.
2. `images/` — the six source scene illustrations (`01-call`, `02-phone`, `03-recording`, `04-door`, `05-table`, `06-stay`). No README lists what uploading them here would entail, so they were left out of the repository rather than guessed at.

The finished deliverables themselves are unaffected: `the-last-call.mp4` was decoded end to end and is intact.

## Creative direction

Immediate hook: a son receives a call three days after his father's funeral. The scheduled-recording reveal resolves the supernatural question while opening an emotional one: what is his mother hiding? A dinner table set for two pays it off visually. The son stays rather than delivering an explanatory moral or an engagement-bait call to action.

The original audio runs approximately 52.2 seconds. The film runs 53 seconds, allowing a short closing hold. Six illustrations are cut into eleven framings with restrained slow zooms; no animated character motion or lip sync is claimed. No music is included.

## Caption reuse

`tools/clipper/` is a read-only local subset copied from `Moroccan791/system`, branch `arena/14b1cc76-system`. The source commit is pinned in `tools/SOURCE.json`. Existing Moonshine transcription, energy alignment, cue grouping and ASS rendering are reused rather than rebuilding the caption system. Font assets and their license are included locally.

Caption text is corrected to the known narration script. Word timings are energy-aligned approximations, not native forced-alignment timestamps; they should receive a human playback review before publication. This is a first cut, not an empirically tested retention result.

## Re-render

Python dependencies: `imageio-ffmpeg`, `pillow`, `numpy`, `moonshine-cpp` (the latter only for preparing a new transcript).

```bash
python -m venv .venv
# Activate .venv using the command for your operating system.
# macOS / Linux:
source .venv/bin/activate
python -m pip install -r requirements.txt
PYTHONPATH="$PWD/tools" python prepare.py
python render.py
```

The second command reuses the saved transcript, makes captions and renders the film. FFmpeg comes from the imageio wheel and includes libass. Final validation decodes the full MP4 to check for media errors. Intermediate video segments are in `work/` and need not be published or committed. The original text used `$PWD/tools`; in this folder layout the scripts fall back to the repository root, so `PYTHONPATH` can simply be left unset once `tools/` is restored there.

## Watch locally

```bash
cd post1
python -m http.server 8080
```

Open `http://localhost:8080` in your own browser. The player includes a download button. GitHub itself may offer the MP4 as a download rather than an inline video.
