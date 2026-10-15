# motion/ — animated shots from stills

A CPU-only motion renderer. It takes one of the six illustrations and produces a moving shot, instead of the linear `zoompan` push that `post1/render.py` uses today.

It exists to answer one question: **can this pipeline animate without a GPU or a paid video model?** Yes — the motion is cheap. What it cannot do is invent new artwork or make characters act.

## Watch it

[`COMPARE.mp4`](COMPARE.mp4) — the same frame, three ways, side by side:

| Panel | What it is |
| --- | --- |
| **NOW** | What `post1/render.py` does today: still + linear zoom |
| **LIVING** | Slow eased camera + lamp that breathes/flickers + dust motes + grain |
| **PARALLAX** | Depth-displaced pixels (near things slide further) + handheld drift + roll |

Individual clips: [`example-living.mp4`](example-living.mp4) · [`example-parallax.mp4`](example-parallax.mp4)

## Use it

```bash
pip install numpy opencv-python-headless imageio-ffmpeg
python motion/motion.py SOURCE.png OUT.mp4 living          # or: parallax | comparison
python motion/motion.py SOURCE.png OUT.mp4 living 8        # optional duration, default 6s
```

Source images must be 1080×1920. If you still have `post1/images/`, use those. Otherwise extract a clean frame from the finished film — these shots have no captions burned in while the camera is still:

```bash
FF=$(python -c "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())")
$FF -ss 0.6 -i post1/the-last-call.mp4 -frames:v 1 01-call.png
```

## What it actually does

1. **Eased multi-keyframe camera** — zoom, pan and roll interpolated with smoothstep, not a linear ramp, so the move starts and stops.
2. **2.5D parallax** — a depth proxy (blurred luminance blended with screen height) displaces pixels, so foreground furniture travels further than the wall behind it. Displacement is windowed to zero at both ends so there is no visible snap.
3. **Practical light** — the lamp's radial glow gains a slow breath plus occasional flicker events.
4. **Dust motes** — drift through the light cone, visible only while the lamp is up.
5. **Film finish** — grain, a breathing exposure curve, and a vignette.

Cost: roughly **6 seconds of shot per 35 seconds of CPU** on 2 cores at 1080×1920, H.264 CRF 19. It is ~20× faster than the first draft because motes are painted into small patches rather than full-frame masks.

## Limits — read before planning around it

- **It cannot invent artwork.** No new characters, no new angles, no faces turning, no lip sync. If a shot does not exist as an illustration, this will not create it.
- **Faces will distort** under parallax if the depth proxy misreads them. Keep `parallax` for rooms and objects; use `living` for anything with a person in it.
- **One still per shot, so a pan is limited to the image edges.** For a longer shot, render the source larger or generate the illustration with margin.
- **Nothing is animated *within* the frame** — no candle flame changing shape, no liquid moving, no wind. Only the camera and the light move.
- **It is not a replacement for a text-to-video model.** For characters that move and act, see the options below.

## If you want true generative motion

Check what your own machine has — this sandbox has no GPU and cannot reach those APIs:

| Route | Runs where | Notes |
| --- | --- | --- |
| **Local image-to-video** — LTX-Video, CogVideoX, Wan 2.1/2.2 | Your GPU | Open weights, free, image-to-video. Best current value if you have the VRAM. |
| **Hosted APIs** — Kling, Runway, Luma, Pika, Veo, Sora | Anywhere | Paid per clip, strongest quality, easiest to scale to a whole episode. |
| **Anything you pick** | — | Feed it the illustration + a motion prompt per shot, then cut the results with this pipeline's existing caption and shot-assembly code. |

The captions, timing and assembly in `post1/` do not care how a shot was produced, so a generated clip can drop straight into the place of a still.
