import numpy as np, subprocess, sys
from scipy.ndimage import gaussian_filter, map_coordinates
src=sys.argv[1]; out=sys.argv[2]; nfr=int(sys.argv[3]) if len(sys.argv)>3 else 999
N=1440; FPS=30
SX0,SW,SY0,SH=[float(v) for v in (sys.argv[4] if len(sys.argv)>4 else "380,560,0,520").split(",")]
# read source as grayscale 960x540 frames
W0,H0=960,540
p=subprocess.Popen(['ffmpeg','-v','error','-i',src,'-vf',f'scale={W0}:{H0},setpts=2.0*PTS,minterpolate=fps={FPS}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir,format=gray','-f','rawvideo','-'],stdout=subprocess.PIPE)
enc=subprocess.Popen(['ffmpeg','-v','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{N}x{N}','-r',str(FPS),'-i','-','-c:v','libx264','-crf','14','-pix_fmt','yuv420p','-g','1',out],stdin=subprocess.PIPE)
rng=np.random.default_rng(3)
yy,xx=np.mgrid[0:N,0:N].astype(np.float32)
# plaster texture
tex=gaussian_filter(rng.standard_normal((N,N)).astype(np.float32),1.2)*0.018+gaussian_filter(rng.standard_normal((N,N)).astype(np.float32),18)*0.05
base=np.array([0.925,0.895,0.845],np.float32)  # warm off-white wall
# sun patch: skewed soft parallelogram (window light) coming from upper-left
u=(xx-0.10*N)+0.35*(yy-0.0*N)
v=yy
sun=(1/(1+np.exp(-(u-0.18*N)/14)))*(1/(1+np.exp((u-1.05*N)/18)))*(1/(1+np.exp(-(v-0.06*N)/14)))*(1/(1+np.exp((v-0.92*N)/16)))
sun=sun.astype(np.float32)
# vignette ambient falloff
amb=(0.80-0.10*((xx/N-0.5)**2+(yy/N-0.45)**2)*2).astype(np.float32)
i=0
while i<nfr:
    raw=p.stdout.read(W0*H0)
    if len(raw)<W0*H0: break
    g=np.frombuffer(raw,np.uint8).reshape(H0,W0).astype(np.float32)/255
    # region: right-top area with more sky; map wall coords -> source coords with shear (projected shadow)
    sx=SX0+ (xx/N)*SW + (yy/N)*60
    sy=SY0+ (yy/N)*SH - (xx/N)*40
    m=map_coordinates(g,[sy.ravel()/1.0,sx.ravel()],order=1,mode='reflect').reshape(N,N)
    lit=np.clip((m-0.30)/0.25,0,1)  # sky bright -> lit
    lit=gaussian_filter(lit,6.5)     # penumbra
    light=amb+ sun*lit*0.30 - (1-sun)*0.0
    col=base[None,None,:]*(light[...,None]) * np.array([1.0,0.985,0.95])[None,None,:]**(1-lit[...,None])
    # warm the lit areas slightly
    col=col+ (sun*lit)[...,None]*np.array([0.06,0.035,0.0],np.float32)
    col=col*(1+tex[...,None])
    col=np.clip(col,0,1)
    enc.stdin.write((col*255).astype(np.uint8).tobytes()); i+=1
enc.stdin.close(); enc.wait(); print('frames',i)
