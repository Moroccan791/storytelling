"""Render a standalone story using generated assets and existing clipper captions.
Run: /home/user/storytelling/.venv/bin/python render.py
"""
from pathlib import Path
import concurrent.futures, difflib, json, re, subprocess, sys
import imageio_ffmpeg
from PIL import Image, ImageOps
ROOT=Path(__file__).resolve().parent
# Post files live in post1/; the shared clipper subset stays at the repo root.
TOOLS=ROOT/'tools' if (ROOT/'tools').is_dir() else ROOT.parent/'tools'
sys.path.insert(0,str(TOOLS))
from clipper.asr.base import Word
from clipper.captions.ass import write_ass
from clipper.captions.cues import group_words
from clipper.config import DEFAULT_STYLE, deep_merge
FF=imageio_ffmpeg.get_ffmpeg_exe()
WORK=ROOT/'work'; WORK.mkdir(exist_ok=True)
SCRIPT='''Three days after we buried my father, he called to warn me about my mother.
“She’s going to lie to you tonight,” he said. “Don’t believe her.”
I dropped the phone. Then his voice continued.
“If this worked, you’ve already figured out it’s a recording. Your sister helped me schedule it.”
Dad had been sick for months. Apparently, he’d been planning more than his funeral.
“Your mother will say she’s fine. She’ll tell you to go home. Don’t.”
That evening, Mum opened the door with a smile.
“I’m fine, sweetheart. You should go.”
Behind her, the table was set for two.
I took off my coat.
“Actually, Mum… I’m hungry.”
And for the first time since the funeral, she cried.'''
(ROOT/'script.txt').write_text(SCRIPT+'\n')

def run(args):
 p=subprocess.run([FF,'-nostdin','-y','-hide_banner','-loglevel','error',*args],capture_output=True,text=True)
 if p.returncode: raise RuntimeError(p.stderr[-4000:])

# Restore the approved script's punctuation and words to measured ASR timings.
# Timing is energy-aligned, not native word timestamps; source is retained.
raw=json.loads((ROOT/'transcript-asr.json').read_text())['words']
tokens=SCRIPT.split()
def norm(x): return re.sub('[^a-z0-9]','',x.lower())
matcher=difflib.SequenceMatcher(a=[norm(w['text']) for w in raw],b=[norm(t) for t in tokens],autojunk=False)
words=[]
for tag,a,b,c,d in matcher.get_opcodes():
 if tag=='equal':
  words.extend(Word(text=tokens[j],start=raw[i]['start'],end=raw[i]['end'],source='moonshine/energy-align') for i,j in zip(range(a,b),range(c,d)))
 elif tag=='replace':
  start,end=raw[a]['start'],raw[b-1]['end']; weights=[max(1,len(norm(t))) for t in tokens[c:d]]; total=sum(weights); cursor=start
  for t,w in zip(tokens[c:d],weights):
   stop=cursor+(end-start)*w/total;words.append(Word(t,round(cursor,3),round(stop,3),source='script-corrected/approximate'));cursor=stop
 elif tag=='insert':
  end=raw[a]['start'] if a<len(raw) else raw[-1]['end']+.15
  start=words[-1].end if words else max(0,end-.2)
  if end-start<.07* (d-c):
   start=max(words[-1].start+.05,words[-1].end-.10*(d-c));words[-1].end=start
  step=(end-start)/max(1,d-c)
  for j,t in enumerate(tokens[c:d]):words.append(Word(t,round(start+j*step,3),round(start+(j+1)*step,3),source='script-corrected/approximate'))
(ROOT/'words.json').write_text(json.dumps([w.to_dict() for w in words],indent=2))
style=deep_merge(DEFAULT_STYLE,{'captions':{'font_size_ass':76,'font_family':'Montserrat','outline_width':4,'shadow':1,'position':{'anchor':'bottom_center','cy':.80},'karaoke':{'enabled':True,'highlight_color':'#F5C879'},'animation':{'in':'fade','duration':.08}}})
cues=group_words(words,max_words=4,max_chars=24,max_lines=1,min_duration=.3,max_duration=2.2,gap_break=.4)
write_ass(ROOT/'captions.ass',cues,style,width=1080,height=1920,mode='word')
(ROOT/'style.json').write_text(json.dumps(style,indent=2))
(ROOT/'captions.json').write_text(json.dumps([c.to_dict() for c in cues],indent=2))

# Exact 30 fps cut points. Alternate wide and tight framing rather than
# distracting transitions; the voice track is never cut or time-stretched.
shots=[
 (0,3.05,'01-call',1.00,1.05),
 (3.05,10.7,'01-call',1.14,1.22),
 (10.7,12.7,'02-phone',1.00,1.07),
 (12.7,14.7,'01-call',1.22,1.18),
 (14.7,21.0,'03-recording',1.00,1.06),
 (21.0,26.7,'03-recording',1.12,1.18),
 (26.7,32.7,'01-call',1.10,1.04),
 (32.7,39.3,'04-door',1.00,1.08),
 (39.3,42.6,'05-table',1.00,1.08),
 (42.6,47.8,'06-stay',1.00,1.05),
 (47.8,53.0,'06-stay',1.10,1.16),
]
manifest={'title':'The Last Call','format':'1080x1920, 30 fps','duration_seconds':53,'narration_language':'en','voice':'voice-00','shots':shots,'caption_source':'tools/SOURCE.json','caption_timing_note':'Moonshine ASR + energy alignment, corrected to approved script. Approximate word timings.','music':'none','fiction':True}
(ROOT/'project.json').write_text(json.dumps(manifest,indent=2))

def shot_render(item):
 i,(start,end,name,z0,z1)=item
 n=round(end*30)-round(start*30)
 src=WORK/f'{name}.png'
 if not src.exists():
  image=Image.open(ROOT/'images'/f'{name}.png').convert('RGB')
  ImageOps.fit(image,(1440,2560),method=Image.Resampling.LANCZOS).save(src)
 dest=WORK/f'shot-{i:02d}.mp4'
 zoom=f'{z0}+({z1-z0})*on/{max(1,n-1)}'
 vf=f"zoompan=z='{zoom}':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d={n}:s=1080x1920:fps=30,setsar=1"
 run(['-threads','2','-i',str(src),'-vf',vf,'-frames:v',str(n),'-an','-c:v','libx264','-threads','2','-preset','fast','-crf','20','-pix_fmt','yuv420p',str(dest)])
 print(f'Shot {i+1}/{len(shots)} rendered',flush=True)
 return dest

if not (ROOT/'images').is_dir():
 raise SystemExit('Missing images/ - restore the six scene illustrations before re-rendering.')

# Prepare source crops serially to avoid simultaneous writes to reused images.
for name in {s[2] for s in shots}:
 src=WORK/f'{name}.png'
 if not src.exists(): ImageOps.fit(Image.open(ROOT/'images'/f'{name}.png').convert('RGB'),(1440,2560),method=Image.Resampling.LANCZOS).save(src)
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool: segments=list(pool.map(shot_render,enumerate(shots)))
listing=WORK/'concat.txt';listing.write_text(''.join(f"file '{p.as_posix()}'\n" for p in segments))
run(['-f','concat','-safe','0','-i',str(listing),'-c','copy',str(WORK/'picture.mp4')])
print('Burning existing clipper captions and mastering narration...',flush=True)
# The local root contains no quote/colon characters needing filter escaping.
filters=f"subtitles={ROOT/'captions.ass'}:fontsdir={ROOT/'tools/assets/fonts'},fade=t=out:st=52.6:d=0.4"
run(['-threads','2','-i',str(WORK/'picture.mp4'),'-i',str(ROOT/'narration.mp3'),'-vf',filters,'-af','loudnorm=I=-16:TP=-1.5:LRA=9,apad','-map','0:v:0','-map','1:a:0','-t','53','-c:v','libx264','-threads','2','-preset','fast','-crf','19','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-ar','48000','-movflags','+faststart',str(ROOT/'the-last-call.mp4')])
# Decode the entire final file: fail rather than presenting a corrupt render.
run(['-i',str(ROOT/'the-last-call.mp4'),'-f','null','-'])
run(['-ss','40.8','-i',str(ROOT/'the-last-call.mp4'),'-frames:v','1',str(ROOT/'preview.jpg')])
print('Done:',ROOT/'the-last-call.mp4',flush=True)
