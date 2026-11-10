"""Find the MPR6 bank whose $DFB6 bytes match the game's 74-byte check."""
import glob

disc = open('build/extracted/data/track_02.bin', 'rb').read()
target = disc[0x830:0x830 + 74]     # logical $3020 in the boot block

for path in sorted(glob.glob('*.pce')):
    rom = open(path, 'rb').read()
    print('== %s' % path)
    hits = []
    for mpr6 in range(256):
        phys = (mpr6 << 13) | (0xDFB6 & 0x1FFF)
        if phys + 74 > len(rom):
            continue
        chunk = rom[phys:phys + 74]
        same = sum(1 for a, b in zip(chunk, target) if a == b)
        if same >= 8:
            hits.append((same, mpr6, phys))
    hits.sort(reverse=True)
    if hits:
        for same, mpr6, phys in hits[:6]:
            print('   MPR6=$%02X -> physical $%05X : %d/74 match' % (mpr6, phys, same))
    else:
        print('   no bank matches (best < 8/74)')
    print('   reference at physical $3FFB6 : %d/74'
          % sum(1 for a, b in zip(rom[0x3FFB6:0x3FFB6 + 74], target) if a == b))
    print()
