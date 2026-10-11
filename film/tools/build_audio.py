"""Builds film_audio.wav: the song edited to the beat map + every SFX placed by its measured peak.
usage: python3 build_audio.py <song.mp3> <sfx_dir> <sfx_events.json> <out_dir>"""
import numpy as np, subprocess, json, sys, os
SR = 48000
song, sfxdir, evfile, outdir = sys.argv[1:5]

def load(path, extra=None):
    cmd = ['ffmpeg', '-v', 'error', '-i', path]
    if extra: cmd += ['-af', extra]
    cmd += ['-ac', '2', '-ar', str(SR), '-f', 'f32le', '-']
    return np.frombuffer(subprocess.run(cmd, capture_output=True).stdout, np.float32).reshape(-1, 2).copy()

# ---- song: Mixkit "Talent in the Air" measured at 121.72 BPM -> stretched to exactly 120 ----
SRC_BPM, FIRST = 121.72, 0.0067   # first-beat onset, measured
k = SRC_BPM / 120.0
y = load(song, f'rubberband=tempo={120.0 / SRC_BPM:.6f}:transients=crisp')
tb = lambda beat: (FIRST + beat * 60 / SRC_BPM) * k        # beat time in the stretched song
seg = lambda b0, b1: y[int(tb(b0) * SR):int(tb(b1) * SR)]
from scipy.signal import butter, sosfilt, find_peaks
_lo = sosfilt(butter(4, [40, 120], 'bandpass', fs=SR, output='sos'), y.mean(1))
_env = np.convolve(np.abs(_lo), np.ones(240) / 240, 'same'); _dv = np.maximum(0, np.diff(_env, prepend=0))
def onset_fix(b0, b1):
    # measured kick onsets inside [b0, b1) vs the beat grid -> correction in seconds
    a, z = int(tb(b0) * SR), int(tb(b1) * SR)
    d = _dv[a:z]; pk, _ = find_peaks(d, distance=int(0.35 * SR), height=d.max() * 0.3)
    tp = (pk + a) / SR; res = ((tp - tb(b0) + 0.25) % 0.5) - 0.25
    print(f'segment {b0}-{b1}: {len(tp)} kicks, median offset {np.median(res) * 1000:.1f} ms')
    return float(np.median(res)) if len(tp) >= 2 else 0.0
DUR = 30.0
mix = np.zeros((int((DUR + 0.6) * SR), 2), np.float32)
XF = int(0.008 * SR)
def place(chunk, at, fade_in=True):
    i = int(at * SR)
    c = chunk.copy()
    if fade_in: c[:XF] *= np.linspace(0, 1, XF)[:, None]
    c[-XF:] *= np.linspace(1, 0, XF)[:, None]
    n = min(len(c), len(mix) - i); mix[i:i + n] += c[:n]
PRE = 0.006   # cut a hair before each downbeat transient
# A: end of breakdown + riser (b1-b16) -> drop (b17) -> 32 beats of groove (to b48)
fa = onset_fix(128, 160)
a = y[int((tb(112) + fa) * SR):int((tb(160) + fa - PRE) * SR)]
place(a, 0.0 - 0.0, fade_in=False)
# B: the drop-out into the quiet breakdown (b49-b56) under the flood / wall
fb = onset_fix(88, 96)
b = y[int((tb(96) + fb - PRE) * SR):int((tb(104) + fb - PRE) * SR)]
place(b, 24.0 - PRE)
# C: the drop again — the wordmark springs back on it (b57-b60), tail faded
c = y[int((tb(128) + fa - PRE) * SR):int((tb(128) + fa + 2.55) * SR)].copy()
fl = int(0.55 * SR); c[-fl:] *= np.linspace(1, 0, fl)[:, None] ** 2
place(c, 28.0 - PRE)
music = mix.copy()
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'f32le', '-ar', str(SR), '-ac', '2', '-i', '-', os.path.join(outdir, 'music_stem.wav')], input=music[:int(DUR * SR)].astype(np.float32).tobytes())

# ---- SFX, each placed by its measured peak ----
MAP = {  # name: (mixkit id, seconds kept around the peak: pre, post)
 'click': (2569, .05, .4), 'sweep_small': (1478, .2, .35), 'bubble_click': (3069, .02, .5), 'tick': (1137, .05, .35),
 'check_soft': (2578, .2, .5), 'shutter_lens': (1434, .15, .3), 'shutter': (1430, .15, .45), 'paper_slide': (1104, .15, .3),
 'paper_quick': (3120, .12, .6), 'swoosh_fast': (1487, .17, .12), 'tech_slide': (1523, .34, .8), 'msg_pop': (3005, .04, .14),
 'pop_egg': (1317, .12, .3), 'light_button': (2579, .06, .1), 'zoom_in': (3118, .29, .55), 'water_bubble': (3000, .05, .6),
 'liquid_bubble': (1321, .11, .9), 'glass_slide': (1902, .5, .5), 'wand': (2342, .6, 1.4), 'liquid_bubble2': (759, .02, .8),
 'autofocus': (1436, .3, .4), 'lock': (2853, .02, .8), 'zoom_move': (2860, .15, .9), 'bleep_conf': (2602, .35, .7),
 'zoom_out': (2529, .15, 1.0), 'hard_pop': (2364, .04, .6), 'sparkle': (2343, .6, .9), 'calc': (2636, .73, .2),
 'paper_slice': (2386, .5, .2), 'confirm': (2867, .19, .8), 'pass_by': (3161, 1.2, .8), 'notif': (914, .48, .5),
 'correct': (2358, .03, .45), 'bass_trans': (3114, .35, .85), 'whoosh_fast': (1491, .3, .8), 'rumble': (1695, .8, 1.2),
 'long_pop': (2364, .04, .8),
}
cache = {}
def sfx(name):
    if name in cache: return cache[name]
    sid, pre, post = MAP[name]
    s = load(os.path.join(sfxdir, f'{sid}.wav'))
    env = np.convolve(np.abs(s).mean(1), np.ones(240) / 240, 'same')
    pk = int(np.argmax(env))
    a0, a1 = max(0, pk - int(pre * SR)), min(len(s), pk + int(post * SR))
    s = s[a0:a1].copy(); pk -= a0
    f = min(int(0.04 * SR), len(s) // 3); s[-f:] *= np.linspace(1, 0, f)[:, None]
    s /= (np.abs(s).max() + 1e-9)              # peak-normalise, gain set per event
    cache[name] = (s, pk); return cache[name]
events = json.load(open(evfile))
fx = np.zeros_like(mix)
for t, name, db in events:
    s, pk = sfx(name)
    i = int(t * SR) - pk
    g = 10 ** (db / 20)
    if i < 0: s = s[-i:]; i = 0
    n = min(len(s), len(fx) - i); fx[i:i + n] += s[:n] * g
total = (music * 0.9 + fx)[:int(DUR * SR)]
raw = os.path.join(outdir, 'mix_raw.wav')
import wave
pcm = np.clip(total, -1, 1)
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'f32le', '-ar', str(SR), '-ac', '2', '-i', '-', raw], input=pcm.astype(np.float32).tobytes())
# two-pass loudnorm to -14 LUFS
r = subprocess.run(['ffmpeg', '-hide_banner', '-i', raw, '-af', 'loudnorm=I=-14:TP=-1.0:LRA=11:print_format=json', '-f', 'null', '-'], capture_output=True, text=True).stderr
js = json.loads(r[r.rfind('{'):r.rfind('}') + 1])
af = (f"loudnorm=I=-14:TP=-1.0:LRA=11:measured_I={js['input_i']}:measured_TP={js['input_tp']}:measured_LRA={js['input_lra']}"
      f":measured_thresh={js['input_thresh']}:offset={js['target_offset']}:linear=true:print_format=summary")
out = os.path.join(outdir, 'film_audio.wav')
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', raw, '-af', af, '-ar', str(SR), out])
r = subprocess.run(['ffmpeg', '-hide_banner', '-i', out, '-af', 'ebur128=peak=true', '-f', 'null', '-'], capture_output=True, text=True).stderr
print(r[r.rfind('Summary'):])
