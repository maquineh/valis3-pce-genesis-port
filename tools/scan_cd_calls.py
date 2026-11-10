b = open('build/extracted/data/track_02.bin', 'rb').read()
for sec in (968, 1172, 32, 976):
    data = b''.join(b[(sec + i) * 2352 + 16:(sec + i) * 2352 + 16 + 2048]
                    for i in range(8))
    print('=== sector %d (%d bytes) ===' % (sec, len(data)))
    for off in range(len(data) - 3):
        if data[off] == 0x20 and data[off + 1] in (0x12, 0x18, 0x09, 0x0F, 0x15) and data[off + 2] == 0xE0:
            name = {0x12: 'cd_play', 0x18: 'cd_pause', 0x09: 'cd_read',
                    0x0F: 'cd_exec', 0x15: 'cd_search'}[data[off + 1]]
            print('  +$%04X JSR $E0%02X %s' % (off, data[off + 1], name))
