"""Synthetic speech-like signal, classroom-like noise and a reverberation model (known ground truth for tests)."""
import numpy as np
from scipy import signal
SR = sr = 16000
def speechlike(sec, seed=0):
    rng=np.random.default_rng(seed)
    x=np.zeros(sr*sec); truth=np.zeros(sr*sec,bool); pos=0.3
    while pos<sec-1:
        d=rng.uniform(0.4,0.9); f0=rng.uniform(100,200); n=int(d*sr); tt=np.arange(n)/sr
        s=sum(np.sin(2*np.pi*f0*k*tt)/k for k in range(1,15))*(1+0.5*np.sin(2*np.pi*4*tt))*np.hanning(n)
        a=int(pos*sr); x[a:a+n]+=s; truth[a:a+n]=True; pos+=d+rng.uniform(0.3,0.7)
    return x/np.abs(x).max()*0.5, truth
def classroom_noise(n, seed=1):
    rng=np.random.default_rng(seed); t=np.arange(n)/sr
    w=rng.standard_normal(n)
    pink=signal.lfilter([1],[1,-0.95],w)            # low-frequency heavy "fan/traffic"
    hum=0.3*np.sin(2*np.pi*120*t)
    babble=signal.lfilter([1],[1,-0.6],rng.standard_normal(n))*(0.5+0.5*np.sin(2*np.pi*0.2*t)**2)  # non-stationary
    z=pink/pink.std()+hum+0.5*babble/babble.std()
    return z/z.std()
def mix(clean,noise,snr_db):
    g=np.sqrt((clean**2).sum()/((noise**2).sum()*10**(snr_db/10))); return clean+g*noise, g*noise
def rir(rt60, seed=2):
    rng=np.random.default_rng(seed); n=int(rt60*sr); t=np.arange(n)/sr
    h=rng.standard_normal(n)*np.exp(-3*np.log(10)*t/rt60); h[0]=3*np.abs(h).max(); return h/np.abs(h).sum()
def snr(ref,est):
    g=(est@ref)/(ref@ref); return 10*np.log10((g*g*(ref@ref))/(((est-g*ref)**2).sum()))
