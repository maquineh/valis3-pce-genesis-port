"""Capture native city states from a user supplied Japanese Genesis cartridge.

This is an extraction aid, not a playthrough verifier. --assist-health replenishes
retail HP/lives in work RAM; --assist-flight prevents rooftop falls. Neither the
ROM nor captured VRAM/CRAM pixels is patched. Omit flight when approaching the
boss entrance so the retail ground trigger can run. START advances dialogue.
The companion packer documents the named capture directories used for this port.
"""
from pathlib import Path
import argparse
import ctypes as ct
import struct
import sys
import zlib
import test_megacd_libretro as harness


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('core','system','rom','resume','output'):
        parser.add_argument('--'+key,type=Path,required=True)
    parser.add_argument('--frames',type=int,default=3000)
    parser.add_argument('--assist-health',action='store_true')
    parser.add_argument('--assist-flight',action='store_true')
    args=parser.parse_args()
    if args.frames<=0:parser.error('frames must be positive')
    args.output.mkdir(parents=True,exist_ok=True)
    core=ct.CDLL(str(args.core.resolve()))
    core.retro_unserialize.argtypes=[ct.c_void_p,ct.c_size_t]
    core.retro_unserialize.restype=ct.c_bool
    core.retro_serialize_size.restype=ct.c_size_t
    core.retro_serialize.argtypes=[ct.c_void_p,ct.c_size_t]
    core.retro_serialize.restype=ct.c_bool
    core.retro_get_memory_data.argtypes=[ct.c_uint]
    core.retro_get_memory_data.restype=ct.c_void_p
    original_run=core.retro_run
    raw=zlib.decompress(args.resume.read_bytes())
    if raw[:16]!=b'GENPLUS-GX 1.7.6':raise ValueError('unsupported capture state')
    tick=0
    def run():
        nonlocal tick
        if tick==0:
            buffer=ct.create_string_buffer(raw)
            if not core.retro_unserialize(buffer,len(raw)):raise RuntimeError('cannot restore retail state')
        if tick%8==0:
            size=core.retro_serialize_size();buffer=ct.create_string_buffer(size)
            if not core.retro_serialize(buffer,size):raise RuntimeError('cannot capture retail state')
            (args.output/f's{tick}.z').write_bytes(zlib.compress(buffer.raw,1))
        memory=core.retro_get_memory_data(2)
        if args.assist_health:
            ct.memmove(memory+0xf446,struct.pack('<HH',24,24),4)
            ct.memmove(memory+0xf458,struct.pack('<H',9),2)
        if args.assist_flight and ct.c_uint16.from_address(memory+0xf42a).value>128:
            ct.memmove(memory+0xf42a,struct.pack('<H',120),2)
        original_run();tick+=1
    core.retro_run=run
    # Reuse the existing callback/video harness with this same DLL handle.
    harness.ct.CDLL=lambda *unused,**kwargs:core
    harness.event_pressed=lambda events,f,b: b==7 or (b==1 and f%25<5) or (b==3 and f%120<4)
    sys.argv=['capture','--core',str(args.core),'--system',str(args.system),'--cue',str(args.rom),
              '--output',str(args.output),'--script-only','--frames',str(args.frames),'--no-audio-file']
    for frame in range(0,args.frames,200):sys.argv+=['--capture',str(frame)]
    harness.main()

if __name__=='__main__':main()
