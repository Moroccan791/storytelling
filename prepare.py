"""Reuse read-only clipper helpers; no changes to either GitHub repository."""
from pathlib import Path
import sys, json
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools'))
from clipper.ffmpeg import decode_audio
from clipper.asr.moonshine import MoonshineProvider

rate=16000
audio=decode_audio(ROOT/'narration.mp3',rate=rate)
transcript=MoonshineProvider(chunk_seconds=5).transcribe(audio,rate)
(ROOT/'transcript-asr.json').write_text(json.dumps(transcript.to_dict(),indent=2))
for w in transcript.words:
 print(f'{w.start:6.2f} {w.end:6.2f} {w.text}',flush=True)
