#!/usr/bin/env python3
"""Exercise the Mega CD disc through a libretro core, without a GUI.

The caller supplies the core, the disc, and a system directory containing a
compatible BIOS. No BIOS or original game data is included with this script.
Frames and the core's audio output are saved for inspection; a successful run
does not by itself prove that a particular scene was displayed correctly.
"""
import argparse
import ctypes as ct
import struct
import time
import wave
import zlib
from collections import Counter
from pathlib import Path


class Variable(ct.Structure):
    _fields_ = [('key', ct.c_char_p), ('value', ct.c_char_p)]


class GameInfo(ct.Structure):
    _fields_ = [('path', ct.c_char_p), ('data', ct.c_void_p),
                ('size', ct.c_size_t), ('meta', ct.c_char_p)]


class Geometry(ct.Structure):
    _fields_ = [('base_width', ct.c_uint), ('base_height', ct.c_uint),
                ('max_width', ct.c_uint), ('max_height', ct.c_uint),
                ('aspect_ratio', ct.c_float)]


class Timing(ct.Structure):
    _fields_ = [('fps', ct.c_double), ('sample_rate', ct.c_double)]


class AVInfo(ct.Structure):
    _fields_ = [('geometry', Geometry), ('timing', Timing)]


Environment = ct.CFUNCTYPE(ct.c_bool, ct.c_uint, ct.c_void_p)
Video = ct.CFUNCTYPE(None, ct.c_void_p, ct.c_uint, ct.c_uint, ct.c_size_t)
Audio = ct.CFUNCTYPE(None, ct.c_int16, ct.c_int16)
AudioBatch = ct.CFUNCTYPE(ct.c_size_t, ct.POINTER(ct.c_int16), ct.c_size_t)
InputPoll = ct.CFUNCTYPE(None)
InputState = ct.CFUNCTYPE(ct.c_int16, ct.c_uint, ct.c_uint, ct.c_uint, ct.c_uint)

BUTTONS = {'b': 0, 'y': 1, 'select': 2, 'start': 3, 'up': 4, 'down': 5,
           'left': 6, 'right': 7, 'a': 8, 'x': 9, 'l': 10, 'r': 11}

# Tests may set core options before calling main(), e.g. to mute CD-DA when
# isolating the Mega CD PCM channels.  main() merges these over the defaults.
CORE_OPTIONS = {}


def button_event(value):
    """Parse FRAME:BUTTON:DURATION into a half-open input interval."""
    parts = value.lower().split(':')
    if len(parts) != 3 or parts[1] not in BUTTONS:
        raise argparse.ArgumentTypeError('expected FRAME:BUTTON:DURATION, e.g. 2500:start:4')
    try:
        frame, duration = int(parts[0]), int(parts[2])
    except ValueError as exc:
        raise argparse.ArgumentTypeError('frame and duration must be integers') from exc
    if frame < 0 or duration <= 0:
        raise argparse.ArgumentTypeError('frame must be nonnegative and duration positive')
    return frame, BUTTONS[parts[1]], duration


def event_pressed(events, frame, button):
    return any(key == button and start <= frame < start + duration
               for start, key, duration in events)


def write_png(path, image):
    width, height, pitch, fmt, raw = image
    rows = []
    for y in range(height):
        row = bytearray()
        for x in range(width):
            offset = y * pitch + x * (4 if fmt == 1 else 2)
            value = int.from_bytes(raw[offset:offset + (4 if fmt == 1 else 2)], 'little')
            if fmt == 1:  # XRGB8888
                rgb = ((value >> 16) & 255, (value >> 8) & 255, value & 255)
            elif fmt == 2:  # RGB565
                rgb = (((value >> 11) & 31) * 255 // 31,
                       ((value >> 5) & 63) * 255 // 63, (value & 31) * 255 // 31)
            else:  # RGB1555
                rgb = (((value >> 10) & 31) * 255 // 31,
                       ((value >> 5) & 31) * 255 // 31, (value & 31) * 255 // 31)
            row.extend(rgb)
        rows.append(b'\0' + row)

    def chunk(tag, data):
        return (struct.pack('>I', len(data)) + tag + data +
                struct.pack('>I', zlib.crc32(tag + data)))

    header = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
    path.write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', header) +
                     chunk(b'IDAT', zlib.compress(b''.join(rows))) + chunk(b'IEND', b''))


def main(before_frame=None, after_frame=None, frontend_variables=True):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--core', required=True, type=Path, help='Path to the libretro core')
    parser.add_argument('--system', required=True, type=Path, help='System directory containing BIOS')
    parser.add_argument('--cue', required=True, type=Path, help='Disc CUE path')
    parser.add_argument('--output', required=True, type=Path, help='Directory for PNGs and audio')
    parser.add_argument('--selection', choices=('none', 'up', 'down', 'left', 'right'), default='none')
    parser.add_argument('--frames', type=int, default=3400)
    parser.add_argument('--bios-start-frame', type=int, default=600)
    parser.add_argument('--stage-start-frame', type=int, default=2500)
    parser.add_argument('--return-start-frame', type=int,
                        help='press START again after movement to return to the title')
    parser.add_argument('--event', type=button_event, action='append', default=[],
                        help='add FRAME:BUTTON:DURATION input; may be repeated')
    parser.add_argument('--capture', type=int, action='append', default=[],
                        help='capture an additional frame; may be repeated')
    parser.add_argument('--capture-ram', type=int, action='append', default=[],
                        help='save libretro system RAM at the specified frame; may be repeated')
    parser.add_argument('--script-only', action='store_true',
                        help='disable the default BIOS, stage, and movement input sequence')
    parser.add_argument('--save-dir', type=Path,
                        help='separate persistent save directory, reusable across runs')
    parser.add_argument('--no-audio-file', action='store_true',
                        help='count audio without writing a WAV file')
    args = parser.parse_args()
    for name in ('core', 'cue'):
        path = getattr(args, name).resolve()
        if not path.is_file():
            parser.error('%s not found: %s' % (name, path))
        setattr(args, name, path)
    args.system = args.system.resolve()
    if not args.system.is_dir():
        parser.error('system directory not found: %s' % args.system)
    if args.frames <= 0 or (not args.script_only and
       (args.frames <= max(args.bios_start_frame, args.stage_start_frame) or
        min(args.bios_start_frame, args.stage_start_frame) < 0)):
        parser.error('frames must extend beyond the nonnegative input frame numbers')
    if any(frame + duration > args.frames for frame, _, duration in args.event):
        parser.error('event must end within the requested frames')
    if any(frame < 0 or frame >= args.frames for frame in args.capture):
        parser.error('capture frames must be within the requested frames')
    if any(frame < 0 or frame >= args.frames for frame in args.capture_ram):
        parser.error('RAM capture frames must be within the requested frames')
    if args.return_start_frame is not None and (
        args.return_start_frame < args.stage_start_frame + 450 or
        args.return_start_frame + 120 >= args.frames
    ):
        parser.error('return START must follow movement and leave at least 120 frames')
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=True)
    args.save_dir = (args.save_dir or args.output).resolve()
    args.save_dir.mkdir(parents=True, exist_ok=True)

    # Keep callbacks and their referenced strings alive for the core's lifetime.
    directories = [str(args.system).encode('utf-8'), str(args.save_dir).encode('utf-8')]
    options = {(key.encode() if isinstance(key, str) else key):
               (value.encode() if isinstance(value, str) else value)
               for key, value in CORE_OPTIONS.items()}
    state = {'frame': 0, 'format': 0, 'video': None, 'audio': None,
             'samples': 0, 'nonzero': 0, 'queries': Counter(), 'presses': Counter()}

    # Beetle PCE Fast calls the frontend logger while opening a CUE. Its
    # messages are printf-style varargs. We only need the video/audio callbacks.
    @ct.CFUNCTYPE(None, ct.c_int, ct.c_char_p)
    def quiet_log(level, message):
        pass

    @Environment
    def environment(command, data):
        if command == 27:  # GET_LOG_INTERFACE
            ct.cast(data, ct.POINTER(ct.c_void_p))[0] = ct.cast(quiet_log, ct.c_void_p).value
            return True
        if command == 10:  # SET_PIXEL_FORMAT
            state['format'] = ct.cast(data, ct.POINTER(ct.c_uint))[0]
            return state['format'] in (0, 1, 2)
        if command in (9, 30, 31):  # system, core assets, save directories
            ct.cast(data, ct.POINTER(ct.c_char_p))[0] = directories[0 if command == 9 else 1]
            return True
        if command == 3:  # GET_CAN_DUPE
            ct.cast(data, ct.POINTER(ct.c_bool))[0] = True
            return True
        if command == 16:  # SET_VARIABLES, legacy core options
            if not frontend_variables:
                return True
            values = ct.cast(data, ct.POINTER(Variable))
            i = 0
            while values[i].key:
                if values[i].key not in options:
                    options[values[i].key] = (values[i].value or b'').partition(b';')[2].strip().split(b'|')[0]
                i += 1
            return True
        if command == 15:  # GET_VARIABLE
            value = ct.cast(data, ct.POINTER(Variable))
            selected = options.get(value[0].key)
            if selected is not None:
                value[0].value = selected
                return True
            return False
        if command == 17:  # GET_VARIABLE_UPDATE
            ct.cast(data, ct.POINTER(ct.c_bool))[0] = False
            return True
        if command == 24:  # GET_INPUT_DEVICE_CAPABILITIES
            ct.cast(data, ct.POINTER(ct.c_uint64))[0] = 1 << 1
            return True
        return command in (1, 8, 11, 18, 32, 35)

    @Video
    def video(data, width, height, pitch):
        if data and width and height:
            state['video'] = (width, height, pitch, state['format'], ct.string_at(data, pitch * height))

    @Audio
    def audio(left, right):
        state['samples'] += 1
        state['nonzero'] += bool(left or right)
        if state['audio'] is not None:
            state['audio'].writeframesraw(struct.pack('<hh', left, right))

    @AudioBatch
    def audio_batch(data, count):
        state['samples'] += count
        if count:
            state['nonzero'] += sum(bool(data[i]) for i in range(0, count * 2, 2))
            if state['audio'] is not None:
                state['audio'].writeframesraw(ct.string_at(data, count * 4))
        return count

    @InputPoll
    def input_poll():
        pass

    @InputState
    def input_state(port, device, index, button):
        if port or (device & 255) != 1:
            return 0
        state['queries'][button] += 1
        f, start = state['frame'], args.stage_start_frame
        direction = {'up': 4, 'down': 5, 'left': 6, 'right': 7}.get(args.selection, -1)
        pressed = event_pressed(args.event, f, button) or (not args.script_only and (
                   (args.bios_start_frame <= f < args.bios_start_frame + 4 and button == 3) or
                   (start <= f < start + 4 and button == 3) or
                   (args.return_start_frame is not None and
                    args.return_start_frame <= f < args.return_start_frame + 4 and button == 3) or
                   (start - 10 <= f < start + 5 and button == direction) or
                   (start + 200 <= f < start + 300 and button == 7) or
                   (start + 350 <= f < start + 450 and button == 6)))
        if pressed:
            state['presses'][(f, button)] += 1
        return int(pressed)

    core = ct.CDLL(str(args.core))
    core.retro_get_memory_data.argtypes = [ct.c_uint]
    core.retro_get_memory_data.restype = ct.c_void_p
    core.retro_get_memory_size.argtypes = [ct.c_uint]
    core.retro_get_memory_size.restype = ct.c_size_t
    for name, callback, callback_type in (
        ('retro_set_environment', environment, Environment),
        ('retro_set_video_refresh', video, Video),
        ('retro_set_audio_sample', audio, Audio),
        ('retro_set_audio_sample_batch', audio_batch, AudioBatch),
        ('retro_set_input_poll', input_poll, InputPoll),
        ('retro_set_input_state', input_state, InputState),
    ):
        function = getattr(core, name)
        function.argtypes = [callback_type]
        function(callback)
    core.retro_init()
    loaded = False
    try:
        core.retro_load_game.argtypes = [ct.POINTER(GameInfo)]
        core.retro_load_game.restype = ct.c_bool
        info = GameInfo(str(args.cue).encode('utf-8'), None, 0, None)
        loaded = core.retro_load_game(ct.byref(info))
        if not loaded:
            raise RuntimeError('libretro core refused the disc; check core and BIOS configuration')
        av = AVInfo()
        core.retro_get_system_av_info.argtypes = [ct.POINTER(AVInfo)]
        core.retro_get_system_av_info(ct.byref(av))
        print('Disc loaded; %.3f fps, %.0f Hz; selection %s' %
              (av.timing.fps, av.timing.sample_rate, args.selection), flush=True)
        if not args.no_audio_file:
            state['audio'] = wave.open(str(args.output / 'audio.wav'), 'wb')
            state['audio'].setnchannels(2)
            state['audio'].setsampwidth(2)
            state['audio'].setframerate(round(av.timing.sample_rate))
        start = args.stage_start_frame
        captures = set(args.capture)
        captures.add(args.frames - 1)
        if not args.script_only:
            captures.update((args.bios_start_frame - 1, start - 1, start + 20,
                             start + 199, start + 299, start + 449))
        if args.return_start_frame is not None:
            captures.add(args.return_start_frame + 120)
        began = time.monotonic()
        for frame in range(args.frames):
            state['frame'] = frame
            if before_frame is not None:
                before_frame(core,frame)
            core.retro_run()
            if after_frame is not None:
                after_frame(frame, state['video'])
            if frame in args.capture_ram:
                # RETRO_MEMORY_SYSTEM_RAM is 2. Store the raw core-provided
                # bytes so tests can interpret the target architecture's RAM.
                address = core.retro_get_memory_data(2)
                size = core.retro_get_memory_size(2)
                if not address or not size:
                    raise RuntimeError('libretro core did not expose system RAM')
                (args.output / ('ram_%04d.bin' % frame)).write_bytes(ct.string_at(address, size))
            if frame in captures and state['video']:
                write_png(args.output / ('frame_%04d.png' % frame), state['video'])
                print('frame %d, audio samples %d, nonzero %d' %
                      (frame, state['samples'], state['nonzero']), flush=True)
        print('Completed %d frames in %.1fs; input queries %s; %d input frames asserted' %
              (args.frames, time.monotonic() - began, dict(state['queries']), len(state['presses'])))
    finally:
        if state['audio'] is not None:
            state['audio'].close()
        if loaded:
            core.retro_unload_game()
        core.retro_deinit()


if __name__ == '__main__':
    main()
