"""Extract Cham's request for the sword from the original post-rescue dialogue."""
from pathlib import Path
import sys
import wave
import numpy as np
from scipy.signal import resample_poly, sosfilt, butter

def extract(track, dest):
    with wave.open(str(track),'rb') as w:
        assert (w.getframerate(),w.getsampwidth(),w.getnchannels()) == (44100,2,2)
        w.setpos(round(7.98*44100))
        stereo=np.frombuffer(w.readframes(round((11.6-7.98)*44100)),dtype='<i2').reshape(-1,2)
    # The speaking voice is centered. Filter bass, resample and use a small
    # fade at either cut to keep the PCM channel silent outside the dialogue.
    mid=stereo.astype(np.float64).mean(axis=1)
    voice=resample_poly(sosfilt(butter(2,100,fs=44100,btype='highpass',output='sos'),mid),1,4)
    ramp=np.linspace(0,1,140)
    voice[:len(ramp)]*=ramp
    voice[-len(ramp):]*=ramp[::-1]
    values=np.rint(voice*123/np.max(np.abs(voice))).astype(np.int16)
    encoded=np.where(values>=0,0x80+values,-values).astype(np.uint8)
    # At the end the chip loops on a silent sample. 0xff is reserved.
    assert 0xff not in encoded
    dest.write_bytes(encoded.tobytes()+bytes((0x80,0xff)))

if __name__=='__main__':
    extract(Path(sys.argv[1]),Path(sys.argv[2]))
