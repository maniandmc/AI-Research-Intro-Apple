"""QA: one frame per beat -> contact sheets; frame-difference scan for single-frame pops.
usage: python3 qa.py film.mp4 outdir"""
import numpy as np, subprocess, sys, os
from PIL import Image, ImageDraw
src, out = sys.argv[1], sys.argv[2]; os.makedirs(out, exist_ok=True)
N = 360
raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', src, '-vf', f'scale={N}:{N}', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True).stdout
fr = np.frombuffer(raw, np.uint8).reshape(-1, N, N, 3)
fps = 60
print('frames', len(fr))
# one frame per beat (mid-beat +0.25s shows each beat's action)
for page in range(2):
    sheet = Image.new('RGB', (6 * 240, 5 * 260), 'white'); d = ImageDraw.Draw(sheet)
    for j in range(30):
        b = page * 30 + j + 1
        i = min(len(fr) - 1, int(((b - 1) * 0.5 + 0.25) * fps))
        im = Image.fromarray(fr[i]).resize((240, 240))
        x, y = (j % 6) * 240, (j // 6) * 260
        sheet.paste(im, (x, y)); d.text((x + 4, y + 242), f'b{b}  t={(b - 1) * 0.5 + 0.25:.2f}', fill='black')
    sheet.save(f'{out}/beats_{page + 1}.jpg', quality=88)
# frame-difference spikes
f = fr.astype(np.float32)
diff = np.abs(f[1:] - f[:-1]).mean(axis=(1, 2, 3))
spikes = []
for i in range(2, len(diff) - 2):
    nb = np.median([diff[i - 2], diff[i - 1], diff[i + 1], diff[i + 2]])
    if diff[i] > 3 * max(nb, 0.6) and diff[i] > 2.0:
        spikes.append((i + 1, diff[i], nb))
print('pops (frame, diff, neighbour median):')
for s in spikes: print(f'  frame {s[0]}  t={s[0] / fps:.3f}s  diff={s[1]:.2f}  nb={s[2]:.2f}')
print('first==last mean abs diff:', np.abs(f[0] - f[-1]).mean())
