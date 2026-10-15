# pipeline/ — the on-demand video engine

Two formats share one pipeline. Nothing here renders on its own: it waits for
a spec folder to be filled in.

| Format | Shape | Images | Length |
| --- | --- | --- | --- |
| **A — Story** | Emotional short: hook, one twist, strong last line | 15-25 | 25-45 s |
| **B — Did you know** | One true fact, 2-3 supporting details | 10-18 | 25-45 s |
| **B — What if** | A scenario step by step, ending on the surprising consequence | 10-18 | 25-45 s |

All three output 1080×1920, 30 fps, MP4.

## How a video gets made

```
you pick a format -> I bring scored ideas from TOPICS.md -> you pick one
        |
        v
spec.json  (script, shot plan, headline, sources)
        |
        v
images/*.png   nar/*.wav
        |
        v
python pipeline/build.py --spec pipeline/specs/<id>
        |
        v
videos/<id>/<id>.mp4 + script + captions + sources + report
```

## What the pipeline enforces

`check.py` runs before anything is rendered, and every result — pass or fail —
lands in `report.md`. A build never quietly hides a broken rule.

| Rule | Enforced |
| --- | --- |
| Hook caption on screen within 2 s | yes |
| Image changes every 2-4 s, never held longer than 4 s | yes |
| Zoom or pan on every image, direction alternating | yes |
| 2.5D parallax on key images | yes |
| Captions 2-4 words, one fixed position, lower centre | yes |
| Caption cap height 5-7% of frame | measured from a rendered frame |
| Captions never cover the subject (block starts below 64%) | yes |
| Typing sound under the headline | yes |
| Music bed present, ducked under the voice | yes |
| "Follow for more" once, only at the very end | yes |
| Loop-friendly ending (last image = first image) | yes |
| Image count inside the format's range | yes |
| Every claim backed by 2+ named sources (Format B) | yes |
| Low-confidence claims flagged for review (Format B) | yes |
| Every caption event actually renders visible text | yes |

## Files

| File | Does |
| --- | --- |
| `build.py` | the whole build, from spec to MP4 plus report |
| `camera.py` | per-shot motion: eased zoom/pan, parallax, grain, vignette |
| `audio.py` | synthesised music bed, five sound effects, side-chain ducking, mixing |
| `captions.py` | caption cues, typed headline, end card, ASS writing |
| `check.py` | the rules above |
| `TOPICS.md` | the scored idea bank and the "already made" tracker |
| `smoke_test.py` | builds a synthetic video with no AI assets, and verifies everything |

## Self test

```bash
python pipeline/smoke_test.py
```

Generates test cards and a speech-shaped waveform, builds a 4-shot video, and
verifies the aligner against known word positions, all 20 rule checks, and the
caption geometry measured out of the finished frames. It needs no API keys and
no text-to-speech, so it can be run any time.

It is also the calibration guard: the caption constants in `captions.py` were
wrong twice (a 40% error from trusting font metrics instead of measuring, then
a wrong anchor offset), so the test now measures the rendered cap height and
fails if the constant has drifted.

## Notes on the moving parts

**Timing.** Word timings come from `clipper.align.energy_align.align_words`,
which is given the *known* script text. No ASR pass, so captions cannot drift
from the voice. Measured accuracy on the synthetic probe: ~186 ms mean.

**Audio.** Everything is synthesised — a slow chord pad, a whoosh per cut, a
riser/thud/shimmer for reveals, and soft key clicks under the headline. The
bed sits 26 dB under the voice and is ducked a further 9 dB while speech is
present. No sample library, so no licensing to track.

**Captions.** At the required 5.6% cap height, only ~11 characters fit across
1080 px, so a 2-4 word cue is set on up to two lines. This is the one place
where the shared rules pull against each other, and two lines is how it
resolves without shrinking the text below the 5% floor.

**What the pipeline does not do.** It does not generate images or speech. Art
comes from an image model at 1080×1920; narration comes from text-to-speech
(the voice in use is `voice-00`). Both drop into the spec folder, and the
build is identical either way.
