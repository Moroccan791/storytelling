# storytelling

Standalone storytelling shorts. Each post lives in its own numbered folder with everything it needs — final video, narration, script, captions, render scripts, and posting metadata.

## Posts

| Post | Title | Length | Folder |
| ---- | ----- | ------ | ------ |
| 1 | The Last Call — a son gets a call three days after his funeral | 53 s · 1080×1920 | [`post1/`](post1/) |

## Structure

```
tools/                       shared, read-only caption pipeline (vendored, pinned)
motion/                      CPU motion renderer + recovered source stills
docs/                        animation options, costs and limits
post1/
├── README.md                project notes for this post
├── the-last-call.mp4        final cut (H.264 + AAC, 1080×1920, 30 fps)
├── narration.mp3            generated English voiceover
├── script.txt               approved production script
├── post.md / post.json      title, description, hashtags, ready-to-copy caption
├── index.html               local player (poster + download button)
├── preview.jpg              poster frame
├── project.json             shot plan and production metadata
├── style.json               caption and motion style used for the render
├── captions.ass / .json     subtitles and cue data
├── words.json               word-level timings
├── transcript-asr.json      raw ASR pass over the narration
├── prepare.py / render.py   re-render pipeline
└── requirements.txt         Python dependencies for the pipeline
```

`work/` (intermediate render segments) and `.venv/` are ignored and never committed.

## Shared tooling

The caption pipeline (`tools/clipper/` plus the Montserrat fonts in `tools/assets/fonts/`) is a read-only subset copied from `Moroccan791/system`, branch `arena/14b1cc76-system`. It is shared across posts and vendored at the repository root, pinned by SHA-256 in `tools/SOURCE.json`. See [`tools/README.md`](tools/README.md).

Fixes to it belong upstream in `Moroccan791/system`, not here — re-vendor from `tools/SOURCE.json` afterwards.

## Animated episodes

`motion/` turns illustrations into moving shots — eased camera, practical-light flicker, drifting dust, 2.5D depth parallax — on CPU, no GPU and no paid model. `post1/render_video.py` cuts those clips (or clips from any image-to-video model) onto the shot plan and burns in the same captions and narration.

Measured on 2 CPU cores: **~6 minutes** for a full 53-second episode, start to finish.

It moves the camera and the light only — it cannot invent artwork or animate a character's face. [`docs/ANIMATION.md`](docs/ANIMATION.md) sets out what the target machine can and cannot run, the free Colab route for real generative motion, and current per-episode costs. [`motion/README.md`](motion/README.md) has the comparison video.

## Watching a post locally

```bash
cd post1
python -m http.server 8080
```

Then open `http://localhost:8080` in your own browser — the page plays `the-last-call.mp4` and offers a download button.
