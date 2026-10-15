# Specs

One folder per video. `build.py` reads `spec.json` and writes the video into
`videos/<id>/`.

```
specs/<id>/
├── spec.json            script, shot plan, headline, sfx, sources
├── image-prompts.md     the prompt behind every image (the spec.json list, kept readable)
├── images/*.png         the artwork, 1080x1920
└── nar/*.wav            narration, one file per script segment, in order
```

`_template/spec.json` is the annotated starting point.

## Building

```bash
python pipeline/build.py --spec pipeline/specs/<id>          # build
python pipeline/build.py --spec pipeline/specs/<id> --dry-run # rules only, no render
```

Every build runs the rule checks first and refuses to hide a failure: the
report records each one, pass or fail.

## Where narration comes from

`narration.segments` are the spoken lines as separate wavs, which is what the
current tooling produces. If you have a single continuous voice track, use
`narration.file` instead and the script text will still be aligned to it.

Timings come from `clipper.align.energy_align.align_words`, which takes the
script and the audio and finds where each word is - no ASR pass needed, so
captions cannot drift from the voice the way a re-transcription can.
