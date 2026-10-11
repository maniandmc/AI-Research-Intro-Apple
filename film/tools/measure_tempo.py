import numpy as np,subprocess,sys
from scipy.signal import butter,sosfilt,find_peaks
SR=22050
for f in sys.argv[1:]:
    y=np.frombuffer(subprocess.run(['ffmpeg','-v','error','-i',f,'-ac','1','-ar',str(SR),'-f','f32le','-'],capture_output=True).stdout,dtype=np.float32)
    sos=butter(4,[40,120],'bandpass',fs=SR,output='sos'); lo=np.abs(sosfilt(sos,y))
    env=np.convolve(lo,np.ones(220)/220,'same')[::22]  # 1kHz env
    fs=1000
    # onset = positive derivative peaks
    dv=np.maximum(0,np.diff(env,prepend=0)); dv=np.convolve(dv,np.ones(5)/5,'same')
    pk,_=find_peaks(dv,distance=350,height=np.percentile(dv,97)*0.4)
    tp=pk/fs
    # fit grid: for bpm candidates find best period+phase via least squares on peaks
    best=None
    for bpm in np.arange(118,123,0.002):
        P=60/bpm
        ph=np.angle(np.exp(2j*np.pi*tp/P).sum())
        res=((tp/P-ph/(2*np.pi)+0.5)%1-0.5)
        sc=(np.abs(res)<0.06).sum()
        if best is None or sc>best[0]: best=(sc,bpm,ph)
    sc,bpm,ph=best;P=60/bpm; off=(ph/(2*np.pi))*P%P
    print(f.split('/')[-1],'bpm=%.3f'%bpm,'first beat=%.4f'%off,'hits',sc,'/',len(tp))
