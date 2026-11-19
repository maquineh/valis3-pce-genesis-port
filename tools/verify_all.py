#!/usr/bin/env python3
"""Verify every deliverable of the port end-to-end and print a report."""
import json
import hashlib
import os
import subprocess
import sys
import re

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
failures = 0


def run(cmd, **kw):
    try:
        return subprocess.run([sys.executable] + cmd, cwd=ROOT,
                              capture_output=True, text=True, **kw)
    except OSError as exc:
        return subprocess.CompletedProcess(cmd, 1, "", str(exc))


def line(ok, label, detail=""):
    global failures
    if not ok:
        failures += 1
    print("  %s %-56s %s" % ("PASS" if ok else "FAIL", label, detail))


def root_files(image):
    """Read ISO9660 root-directory file records and validate their extents."""
    pvd = image[16 * 2048:17 * 2048]
    if len(pvd) != 2048 or pvd[:7] != b"\x01CD001\x01":
        raise ValueError("invalid ISO9660 primary volume descriptor")
    root = pvd[156:190]
    start = int.from_bytes(root[2:6], "little") * 2048
    size = int.from_bytes(root[10:14], "little")
    if not size or start + size > len(image):
        raise ValueError("invalid root directory extent")
    directory = image[start:start + size]
    files = {}
    pos = 0
    while pos < len(directory):
        length = directory[pos]
        if not length:
            pos = ((pos // 2048) + 1) * 2048
            continue
        record = directory[pos:pos + length]
        if len(record) < 34 or pos + length > len(directory):
            raise ValueError("invalid directory record")
        name_len = record[32]
        if 33 + name_len > len(record):
            raise ValueError("invalid directory file identifier")
        name = record[33:33 + name_len].decode("ascii").split(";")[0]
        offset = int.from_bytes(record[2:6], "little") * 2048
        file_size = int.from_bytes(record[10:14], "little")
        if not record[25] & 2:
            files[name] = file_size > 0 and offset + file_size <= len(image)
        pos += length
    return files


def main():
    os.chdir(ROOT)
    print("== 1. Source disc extraction ==")
    ok = os.path.isdir("build/extracted/audio")
    wavs = [f for f in os.listdir("build/extracted/audio") if f.endswith(".wav")] \
        if ok else []
    line(ok and len(wavs) == 54, "build/extracted/audio/ with %d CD-DA tracks" % len(wavs),
         "(original soundtrack)")
    data = os.listdir("build/extracted/data") if os.path.isdir("build/extracted/data") else []
    line(len(data) == 18, "build/extracted/data/ with %d data tracks" % len(data))
    inv = run(["tools/audio_inventory.py"])
    rows = [l for l in inv.stdout.splitlines() if re.match(r"^track_\d+\s", l)]
    bad = [l for l in rows if "SILENCE" in l or "MISSING" in l]
    line(inv.returncode == 0 and len(rows) == 54 and not bad,
         "audio_inventory: all 54 tracks present and non-silent",
         "%d rows, %d missing/silent; exit %d %s" %
         (len(rows), len(bad), inv.returncode, inv.stderr.strip()))

    print("== 2. Reverse engineering tools ==")
    tools = ["cue_split", "disasm6280", "block_transfers", "find_bios_calls",
             "decode_cd_calls", "list_vram_reads", "find_maps", "pce_gfx",
             "pce2md", "render_bat", "extract_screens", "mcd_inspect"]
    for t in tools:
        p = "tools/%s.py" % t
        line(os.path.isfile(p), p)

    print("== 3. Extracted PC Engine assets ==")
    for f in ("title_tiles", "title_map", "title_pal",
              "stage1_all_tiles", "stage1_all_maps", "stage1_all_pal",
              "stage2_state_tiles", "stage2_state_maps", "stage2_state_pal",
              "stage2b_state_tiles", "stage2b_state_maps", "stage2b_state_pal",
              "stage3a_state_tiles", "stage3a_state_maps", "stage3a_state_pal",
              "stage2c_state_tiles", "stage2c_state_maps", "stage2c_state_pal",
              "stage2c_green_state_tiles", "stage2c_green_state_maps", "stage2c_green_state_pal",
              "stage2c_b_state_tiles", "stage2c_b_state_maps", "stage2c_b_state_pal",
              "stage2a2_state_tiles", "stage2a2_state_maps", "stage2a2_state_pal",
              "stage1a_state_tiles", "stage1a_state_maps", "stage1a_state_pal",
              "stage4a_state_tiles", "stage4a_state_maps", "stage4a_state_pal",
              "stage2_boss_tiles", "stage2_boss_fire_tiles", "city_items",
              "player_spr"):
        p = "game/res/gfx/%s.bin" % f
        line(os.path.isfile(p), p, "%d bytes" % os.path.getsize(p) if os.path.isfile(p) else "")
    meta = "game/res/gfx/stage1_all.json"
    line(os.path.isfile(meta), "stage 1 placeholder metadata exists")
    sl = run(["tools/test_stage_logic.py"])
    line(sl.returncode == 0 and "ALL PASS" in sl.stdout,
         "tools/test_stage_logic.py (stage 1 resources + streaming logic)")
    ct = run(["tools/test_cpu.py"])
    line(ct.returncode == 0 and "ALL PASS" in ct.stdout,
         "tools/test_cpu.py (HuC6280 core: ALU, block transfers, MPR, ST0/1/2)",
         [l for l in ct.stdout.splitlines() if "FAIL" in l])

    print("== 4. Mega CD build ==")
    line(os.path.isfile("game/makefile"), "game/ (megadev Mega CD project)")
    line(os.path.isfile("game/src/game.c"), "game/src/game.c (title screen module)")
    line(os.path.isfile("game/src/city.c"), "game/src/city.c (Genesis city module)")
    for room in ("street", "meeting", "fall", "roof"):
        path = "game/res/gfx/city_%s.bin" % room
        valid = False
        if os.path.isfile(path):
            with open(path, "rb") as stream:
                data = stream.read()
            width = int.from_bytes(data[:2], "big")
            count = int.from_bytes(data[2:4], "big")
            rows = 32 if room == "fall" else 28
            table = 134 + count * 32 + 256 + (64 + width) * rows * 2 + width * 2
            if room == "fall":
                table += 2 + 8 * int.from_bytes(data[table:table+2], "big")
            valid = (32 <= width <= 96 and 0 < count <= 1280 and
                     data[4:6] == bytes([0, 63]) and table + 38 <= len(data))
        line(valid, "Genesis city %s has tile, palette, map and pose data" % room)
    line(os.path.isfile("game/src/stage2_state.c"),
         "game/src/stage2_state.c (real Stage 2 snapshot module)")
    line(os.path.isfile("game/src/stage2b_state.c"),
         "game/src/stage2b_state.c (real Stage 2B snapshot module)")
    line(os.path.isfile("game/src/stage3a_state.c"),
         "game/src/stage3a_state.c (real Stage 3A snapshot module)")
    line(os.path.isfile("game/src/stage2c_state.c"),
         "game/src/stage2c_state.c (real Stage 2C snapshot module)")
    line(os.path.isfile("game/src/stage2c_green_state.c"),
         "game/src/stage2c_green_state.c (real wrapped Stage 2C scene module)")
    line(os.path.isfile("game/src/stage2c_b_state.c"),
         "game/src/stage2c_b_state.c (real Stage 2C corridor snapshot module)")
    line(os.path.isfile("game/src/stage2a2_state.c"),
         "game/src/stage2a2_state.c (real Stage 2A seaside snapshot module)")
    line(os.path.isfile("game/src/stage2boss_state.c") and
         os.path.isfile("game/res/gfx/stage2_boss_tiles.bin"),
         "game/src/stage2boss_state.c (captured STG2C boss module)")
    line(os.path.isfile("game/res/audio/city_sfx.bin"),
         "game/res/audio/city_sfx.bin (original PCM effects)")
    line(os.path.isfile("game/res/gfx/city_items.bin"),
         "game/res/gfx/city_items.bin (original HUD item icons)")
    print("== 4b. Stage modules match their packed resources ==")
    for name, src in (("stage1a_state", "game/src/stage1a_state.c"),
                      ("stage4a_state", "game/src/stage4a_state.c"),
                      ("stage4a_hw2", "game/src/stage4a_capture.c"),
                      ("stage2_state", "game/src/stage2_state.c"),
                      ("stage2b_state", "game/src/stage2b_state.c"),
                      ("stage3a_state", "game/src/stage3a_state.c"),
                      ("stage2c_state", "game/src/stage2c_state.c"),
                      ("stage2c_green_state", "game/src/stage2c_green_state.c"),
                      ("stage2c_b_state", "game/src/stage2c_b_state.c"),
                      ("stage2a2_state", "game/src/stage2a2_state.c")):
        meta = "game/res/gfx/%s.json" % name
        if not (os.path.isfile(meta) and os.path.isfile(src)):
            line(False, "%s: packed metadata and module source exist" % name)
            continue
        m = json.load(open(meta))
        c = open(src).read()
        line("#define STAGE_SCREENS %d" % m.get("screens", 0) in c,
             "%s: STAGE_SCREENS matches the packed screen count" % name)
        line("#define STAGE_TILES %d" % m.get("tiles", 0) in c,
             "%s: STAGE_TILES matches the packed tile count" % name)
        map_path = "game/res/gfx/%s_maps.bin" % name
        if os.path.isfile(map_path):
            data = open(map_path, "rb").read()
            count = m.get("tiles", 0)
            invalid = sum(1 for i in range(0, len(data) - 1, 2)
                          if (int.from_bytes(data[i:i + 2], "big") & 0x7ff) >= count)
            line(len(data) % 2 == 0 and invalid == 0,
                 "%s: map references uploaded tiles" % name,
                 "%d out of range" % invalid)
        else:
            line(False, "%s: map exists" % name)
    print("== 4c. Title dimensions, tiles and palette ==")
    title_paths = {name: "game/res/gfx/title_%s.bin" % name
                   for name in ("tiles", "map", "pal")}
    title_paths.update(meta="game/res/gfx/title.json", source="game/src/game.c")
    missing = [path for path in title_paths.values() if not os.path.isfile(path)]
    line(not missing, "title resources, metadata and module exist", ", ".join(missing))
    if not missing:
        try:
            with open(title_paths['meta'], encoding='utf-8') as f:
                info = json.load(f)
            with open(title_paths['source'], encoding='utf-8') as f:
                source = f.read()
            values = {}
            for name in ('TILES', 'W', 'H'):
                match = re.search(r'^\s*#define\s+TITLE_%s\s+(\d+)\b' % name,
                                  source, re.M)
                if match:
                    values[name] = int(match.group(1))
            with open(title_paths['tiles'], 'rb') as f:
                tiles = f.read()
            with open(title_paths['map'], 'rb') as f:
                tilemap = f.read()
            with open(title_paths['pal'], 'rb') as f:
                palette = f.read()
            count = values.get('TILES', 0)
            line(values.get('W') == 32 and values.get('H') == 28 and
                 info.get('width') == 256 and info.get('height') == 224 and
                 len(tilemap) == 32 * 28 * 2,
                 "title map is 32x28 cells (256x224)")
            line(0 < count <= 0xB800 // 32 and len(tiles) == count * 32 and
                 info.get('tile_count') == count,
                 "title tile data matches upload and fits below sprite table",
                 "%d tiles, %d bytes" % (count, len(tiles)))
            glyphs = re.search(r'^\s*#define\s+UI_GLYPHS\s+(\d+)\b', source, re.M)
            ui_count = int(glyphs.group(1)) if glyphs else 0
            line(bool(glyphs) and 0 < ui_count and count + ui_count <= 0xB800 // 32,
                 "title and menu font fit below sprite table",
                 "%d title tiles + %d glyphs" % (count, ui_count))
            line(len(tiles) >= 32 and tiles[:32] == bytes(32),
                 "title tile 0 is transparent")
            bad = sum(1 for i in range(0, len(tilemap) - 1, 2)
                      if (int.from_bytes(tilemap[i:i + 2], 'big') & 0x7ff) >= count)
            line(len(tilemap) % 2 == 0 and bad == 0,
                 "title map references uploaded tiles", "%d out of range" % bad)
            words = [int.from_bytes(palette[i:i + 2], 'big')
                     for i in range(0, len(palette) - 1, 2)]
            line(len(palette) == 4 * 16 * 2 and 0 < info.get('palette_count', 0) <= 4 and
                 info.get('palette_entries') == 16 and
                 len(words) == 64 and all(not (w & 0xf111) for w in words),
                 "title palette uses four valid Mega Drive lines")
            line(len(words) == 64 and all(words[n] == 0 for n in (0, 16, 32, 48)),
                 "title palette index zero is transparent black")
        except (ValueError, TypeError, OSError) as exc:
            line(False, "title resource validation", str(exc))
    iso = "build/valis3.iso"
    line(os.path.isfile(iso), iso, "%d bytes" % os.path.getsize(iso)
         if os.path.isfile(iso) else "")
    if os.path.isfile(iso):
        d = open(iso, "rb").read()
        line(d[0:16] == b"SEGADISCSYSTEM  ", "boot sector disc id",
             repr(d[0:16]))
        line(d[0x1F0:0x200].startswith(b"JUE"), "region field", repr(d[0x1F0:0x200]))
        try:
            files = root_files(d)
            line(True, "ISO9660 primary volume and root directory valid")
        except (ValueError, UnicodeError) as exc:
            files = {}
            line(False, "ISO9660 primary volume and root directory valid", str(exc))
        for name in ("IPX.MMD", "GAME.MMD", "STAGE1.MMD", "STAGE2.MMD",
                     "STAGE2B.MMD", "STAGE3A.MMD", "STAGE2C.MMD",
                     "STAGE2CG.MMD", "STAGE2CB.MMD", "STAGE2A2.MMD", "STAGE1A.MMD", "STAGE4A.MMD", "STAGE4AX.MMD",
                     "STG2BOSS.MMD", "SPX.SMD"):
            line(files.get(name, False), "ISO root contains nonempty %s" % name)

    print("== 5. Final disc with the original soundtrack ==")
    line(os.path.isfile("dist/valis3_mcd.cue"), "dist/valis3_mcd.cue exists")
    line(os.path.isfile("dist/valis3_mcd.json"), "dist/valis3_mcd.json exists")
    line(os.path.isfile("dist/valis3_mcd.iso"), "dist/valis3_mcd.iso exists")
    if os.path.isfile(iso) and os.path.isfile("dist/valis3_mcd.iso"):
        with open(iso, "rb") as source, open("dist/valis3_mcd.iso", "rb") as final:
            same = hashlib.sha256(source.read()).digest() == hashlib.sha256(final.read()).digest()
        line(same, "final data track matches the current build")
    if os.path.isfile("dist/valis3_mcd.cue"):
        cue = open("dist/valis3_mcd.cue").read()
        ntracks = cue.count("    INDEX 01")
        line(ntracks == 55 and len(re.findall(r"^\s*TRACK\s+\d+\s+AUDIO\s*$", cue, re.M)) == 54,
             "dist/valis3_mcd.cue with %d tracks" % ntracks)
        line("TRACK 01 MODE1/2048" in cue, "data track is MODE1/2048")
        cue_files = re.findall(r'^\s*FILE\s+"([^"]+)"\s+\S+', cue, re.M)
        missing = [p for p in cue_files if not os.path.isfile(os.path.join("dist", p))]
        line(len(cue_files) == 55 and not missing,
             "cue references 55 existing disc files", "%d missing" % len(missing))
        indexes = re.findall(r'^\s*INDEX\s+01\s+(\S+)\s*$', cue, re.M)
        pregaps = re.findall(r'^\s*PREGAP\s+(\S+)\s*$', cue, re.M)
        line(indexes == ["00:00:00"] * 55 and pregaps == ["00:02:00"] * 54,
             "cue uses file-relative indexes and explicit audio pregaps")
        man = json.load(open("dist/valis3_mcd.json")) if os.path.isfile("dist/valis3_mcd.json") else {}
        line(len(man.get("audio_tracks", [])) == 54,
             "track manifest maps %d disc tracks to the original PCE tracks"
             % len(man.get("audio_tracks", [])))
        tot = sum(t["seconds"] for t in man.get("audio_tracks", []))
        line(tot > 2400, "total original music on the disc", "%.1f min" % (tot / 60))
    print("== %d failure(s) ==" % failures)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
