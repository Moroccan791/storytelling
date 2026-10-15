# Animated episodes — what your laptop can and cannot do

Your machine: **Asus X515JA, i3 10th gen, no dedicated GPU, 128 GB SSD + 1 TB HDD.**

Short version: **you cannot run a generative video model on it, and you do not need to.** Two routes work, and one of them is free and needs nothing but the laptop.

---

## Route 1 — CPU motion (free, on your laptop, works today)

`motion/build_clips.py` + `post1/render_video.py`. It animates the illustrations you already have: eased camera moves, 2.5D depth parallax, lamp flicker, drifting dust, grain.

**Measured on 2 CPU cores** — the same core count as your i3:

| Step | Time |
| --- | --- |
| Animate all 6 illustrations into clips (`motion/build_clips.py`) | **3 min** |
| Assemble the 53-second film + captions + audio (`render_video.py`) | **2 min 48 s** |

So a full episode is about **6 minutes of your laptop's time, per version.** Your i3-1005G1 turbos to 3.4 GHz against the 2.6 GHz I measured on, so treat these as the right ballpark, not exact.

**Ceiling:** it moves the camera and the light. Nothing inside the frame changes shape — no mouth moves, no head turns. For *I'm telling a story* that is often enough; for *the character is talking* it is not.

---

## Route 2 — generate real motion, free, in the cloud

Your laptop has no GPU, so the model runs on someone else's. **Google Colab's free tier gives you a Tesla T4 with 16 GB VRAM**, which is enough for current open-weight image-to-video models.

| Model | Runs on free T4 | Time per short clip |
| --- | --- | --- |
| **LTX-Video** (distilled, few-step) | Yes, comfortably | **6–8 min** |
| **Wan 2.2 14B** GGUF Q4 | Yes, with CPU offload | **12–25 min** |

There are one-click notebooks for both — for example [`staed-web/ltx-image-to-video-colab`](https://github.com/staed-web/ltx-image-to-video-colab) wraps LTX in a Gradio UI with a temporary public link.

**The workflow:** upload one of the recovered stills from `motion/src/`, give it a motion prompt, download the clip, save it as `post1/clips/<name>.mp4`, then run `python post1/render_video.py`. The script trims, retimes or ping-pongs whatever you give it onto the shot plan.

Practical notes:
- **Start with LTX.** It is several times faster; use it to iterate the prompt, then re-render the keepers with Wan for quality.
- **Free Colab disconnects after ~90 minutes idle** and will reclaim a busy session. Work in batches, and keep your clips on Google Drive or your own machine.
- **Render at 720p, not 1080p.** Your film is 1080×1920, but the model's output gets scaled and cropped to fit anyway (`render_video.py` handles that), and 1080p roughly doubles the wait for a difference the vertical crop mostly throws away.
- Colab's free tier has no uptime guarantee and is not for commercial work you depend on. If this becomes a production line, move to paid GPU time.

---

## Route 3 — pay a hosted model (best quality, costs money)

No GPU needed; you upload an image and download a clip. Published API rates as of late 2026:

| Model | Image-to-video | Notes |
| --- | --- | --- |
| **Veo 3.1 Lite** | ~$0.05/sec | Cheapest with audio; 720p |
| **Kling 3.0** | ~$0.084/sec silent, ~$0.126 with audio | Best motion from a still; 15 s max |
| **Luma Ray 3.2** | ~$0.06/sec at 720p / ~$0.24 at 1080p | Cinematic camera moves |
| **Runway Gen-4.5** | ~$0.12/sec | Strongest creative control (motion brush) |

**What this film would cost, as one take per shot:** 53 seconds of screen time ≈ **$2.65** (Veo Lite) to **$6.70** (Kling with audio). Realistically you want two or three takes for a usable one, so budget **$8–20 per episode** at 720p. That is the honest number — not free, but not £100 either.

**Free tiers worth using before you pay:**

| Tool | Free allowance | Catch |
| --- | --- | --- |
| **Kling** | 66 credits/day, no card needed (~6 clips) | Watermark, lower res, **non-commercial only** on free |
| **Runway** | 125 credits, one time (~10 s of Gen-4.5) | One-time, not renewable |
| **Google Flow / Veo** | Small daily credit pool | Watermark; availability varies |

If you plan to publish, remember the free tiers above are for testing — Kling's free tier is explicitly non-commercial and watermarked, and several tools reserve commercial rights for paid plans. Check the terms before you post anything you made on a free tier.

---

## What is still out of reach

**Running a generative model on the X515JA itself — forget it.** These models want 8–16 GB of *VRAM*; you have none, and the system RAM (likely 8 GB, maybe 16) is already busy running Windows. Someone on the internet will tell you LTX runs on CPU. It does, at roughly an hour or more per second of video. Not a workflow.

---

## Recommended sequence

1. **Today, free:** run `motion/build_clips.py` and watch the CPU-motion cut. Decide whether camera-and-light motion is enough for your kind of story. It costs you nothing and six minutes.
2. **If you want real motion:** take the stills in `motion/src/` to free Colab, start with LTX-Video, generate one clip for `01-call`, drop it in `post1/clips/`, and re-run `render_video.py`. One shot, end to end, before committing to all six.
3. **If the quality is there and you want it weekly:** move to a hosted API, budget $8–20 an episode, and keep the free Colab route for experiments.

The captioning, timing and assembly do not care where a clip came from, so you can mix freely — a paid Kling shot for the close-up on his face, free CPU motion for the dinner table.
