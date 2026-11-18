"""Replay the Japanese cartridge kidnapping and sword dive with native dialogue timing."""
import argparse
import ctypes as ct
from pathlib import Path
import sys
import zlib

import test_megacd_libretro as harness


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('core','system','rom','checkpoint','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    args = parser.parse_args()
    initial = zlib.decompress(args.checkpoint.read_bytes())
    if initial[:16] != b'GENPLUS-GX 1.7.6':
        parser.error('expected the Genesis Plus GX 1.7.6 s7248.z checkpoint')
    last_button = -500
    dialog_frames = 0
    push = False

    def before(core, frame):
        nonlocal last_button, dialog_frames, push
        if frame == 0:
            core.retro_unserialize.argtypes = [ct.c_void_p,ct.c_size_t]
            core.retro_unserialize.restype = ct.c_bool
            core.retro_serialize_size.restype = ct.c_size_t
            core.retro_serialize.argtypes = [ct.c_void_p,ct.c_size_t]
            core.retro_serialize.restype = ct.c_bool
            buf = ct.create_string_buffer(initial)
            if not core.retro_unserialize(buf,len(initial)):
                raise RuntimeError('failed to restore the original city')
        buf = ct.create_string_buffer(core.retro_serialize_size())
        if not core.retro_serialize(buf,len(buf)):
            raise RuntimeError('failed to read frame '+str(frame))
        raw = buf.raw
        dialog_frames = dialog_frames+1 if raw[0x22525+18]==14 else 0
        push = dialog_frames>=50 and frame-last_button>=90
        if push:
            last_button=frame
        (args.output/f's{frame}.z').write_bytes(zlib.compress(raw,1))

    harness.event_pressed=lambda events,frame,button: button==7 or (button==3 and push)
    sys.argv=['capture','--core',str(args.core),'--system',str(args.system),'--cue',str(args.rom),
              '--output',str(args.output),'--frames','2315','--script-only','--no-audio-file']
    harness.main(before_frame=before)


if __name__=='__main__':
    main()
