"""Match the disc's boot-block signatures against every System Card present."""
import glob

disc = open('build/extracted/data/track_02.bin', 'rb').read()
boot_signature = disc[0x10:0x10 + 0x4D5]      # the 1237-byte reference
game_signature = disc[0x830:0x830 + 74]       # the 74-byte game check

for path in sorted(glob.glob('*.pce')):
    rom = open(path, 'rb').read()
    print('== %s (%d bytes)' % (path, len(rom)))
    i1 = rom.find(boot_signature)
    print('   1237-byte boot signature: %s'
          % (hex(i1) if i1 >= 0 else 'NOT FOUND'))
    i2 = rom.find(game_signature)
    print('   74-byte game signature : %s'
          % (hex(i2) if i2 >= 0 else 'NOT FOUND'))
    # also check the physical addresses used by v1.0
    print('   v1.0 addresses: $3FAE1 %s, $3FFB6 %s'
          % ('match' if rom[0x3FAE1:0x3FAE1 + 0x4D5] == boot_signature else 'no',
             'match' if rom[0x3FFB6:0x3FFB6 + 74] == game_signature else 'no'))
    print()
