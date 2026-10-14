# storytelling

Standalone storytelling shorts. Each post lives in its own numbered folder with everything it needs — final video, narration, script, captions, render scripts, and posting metadata.

## Posts

| Post | Title | Length | Folder |
| ---- | ----- | ------ | ------ |
| 1 | The Last Call — a son gets a call three days after his funeral | 53 s · 1080×1920 | [`post1/`](post1/) |

## Structure

```
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

The caption pipeline (`tools/clipper/`) is a read-only local subset copied from `Moroccan791/system`. It is shared across posts and lives at the repository root, pinned in `tools/SOURCE.json`. It is **not** currently present in this repository — see "Known gaps" in [`post1/README.md`](post1/README.md).

## Watching a post locally

```bash
cd post1
python -m http.server 8080
```

Then open `http://localhost:8080` in your own browser — the page plays `the-last-call.mp4` and offers a download button.
