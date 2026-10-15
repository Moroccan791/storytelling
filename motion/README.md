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

# one clip at a time
python motion/motion.py SOURCE.png OUT.mp4 living          # or: parallax | comparison
python motion/motion.py SOURCE.png OUT.mp4 living 8        # optional duration, default 6s

# or animate a whole post from its shot plan
python motion/build_clips.py                    # writes post1/clips/*.mp4
cd post1 && python render_video.py --clips-dir clips
```

`build_clips.py` renders one clip per illustration, long enough for the longest shot that uses it. `render_video.py` then cuts those clips onto the shot plan, trims or retimes them to fit, and burns in the same captions and narration as `render.py`.

Measured on 2 CPU cores: **3 min** to animate all six illustrations, **2 min 48 s** to assemble the 53-second film.

## Where the source stills come from

`motion/src/` holds all six illustrations at 1080×1920, committed here. They were **recovered from the finished film** by `extract_stills.py`, because the original `post1/images/` files were never committed and only existed on one machine:

```bash
python motion/extract_stills.py          # finds a caption-free frame per illustration
```

The script reads `captions.json` to find moments where no caption is on screen (captions cover roughly two thirds of the runtime, so every illustration has a clean window) and pulls a frame from the middle of the widest one.

These are decoded from the finished H.264, so they are a slightly compressed, already-framed version of the originals — good enough to animate or to feed an image-to-video model, but if you still have `post1/images/` on the original machine, keep those as the master. They must be 1080×1920.

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

**This sandbox has no GPU, and neither does the target machine** — an i3 Asus X515JA. So generative video is not a local option; the models want 8–16 GB of VRAM and would take an hour or more per second of video on a CPU.

Two routes work around that, both covered in detail — with measured times, current prices and free tiers — in [`docs/ANIMATION.md`](../docs/ANIMATION.md):

| Route | Runs where | Cost |
| --- | --- | --- |
| **Free Colab T4** — LTX-Video (6–8 min/clip) or Wan 2.2 GGUF (12–25 min/clip) | Google's GPU, in your browser | Free |
| **Hosted APIs** — Kling, Veo, Luma, Runway | Anywhere | ~$2.65–6.70 per episode, one take per shot |

`post1/render_video.py` takes clips from any of them: drop `<name>.mp4` into `post1/clips/` and run it. It handles the trims, retimes and fallbacks, and the captions, timing and audio are identical to the original render — so you can mix a paid close-up with free CPU motion for the rest.
