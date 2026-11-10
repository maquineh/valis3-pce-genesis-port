#!/usr/bin/env python3
"""Verify every deliverable of the port end-to-end and print a report."""
import json
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def run(cmd, **kw):
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                          shell=isinstance(cmd, str), **kw)


def line(ok, label, detail=""):
    print("  %s %-56s %s" % ("PASS" if ok else "FAIL", label, detail))


def main():
    print("== 1. Source disc extraction ==")
    ok = os.path.isdir("build/extracted/audio")
    wavs = [f for f in os.listdir("build/extracted/audio") if f.endswith(".wav")] \
        if ok else []
    line(ok, "build/extracted/audio/ with %d CD-DA tracks" % len(wavs),
         "(original soundtrack)")
    data = os.listdir("build/extracted/data") if os.path.isdir("build/extracted/data") else []
    line(len(data) == 18, "build/extracted/data/ with %d data tracks" % len(data))
    inv = run("python3 tools/audio_inventory.py")
    quiet = [l for l in inv.stdout.splitlines() if "SILENCE" in l]
    line("music" in inv.stdout and not quiet,
         "audio_inventory: all tracks contain music (no silent tracks)",
         "%d silent" % len(quiet))

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
              "player_spr"):
        p = "game/res/gfx/%s.bin" % f
        line(os.path.isfile(p), p, "%d bytes" % os.path.getsize(p) if os.path.isfile(p) else "")
    meta = "game/res/gfx/stage1_all.json"
    if os.path.isfile(meta):
        m = json.load(open(meta))
        line(m.get("screens", 0) >= 10,
             "stage 1: %s screens decoded from the PC Engine disc" % m.get("screens"))
    sc = run("python3 tools/screen_chain.py 0x17FF90 0x19440 40")
    line("screens decoded" in sc.stdout,
         "tools/screen_chain.py walks the stage-1 screens",
         [l for l in sc.stdout.splitlines() if "consecutive" in l])
    sl = run("python3 tools/test_stage_logic.py")
    line("ALL PASS" in sl.stdout,
         "tools/test_stage_logic.py (stage 1 resources + streaming logic)")

    print("== 4. Mega CD build ==")
    line(os.path.isfile("game/makefile"), "game/ (megadev Mega CD project)")
    line(os.path.isfile("game/src/game.c"), "game/src/game.c (title screen module)")
    line(os.path.isfile("game/src/stage1.c"), "game/src/stage1.c (stage 1 module)")
    iso = "build/valis3.iso"
    line(os.path.isfile(iso), iso, "%d bytes" % os.path.getsize(iso)
         if os.path.isfile(iso) else "")
    if os.path.isfile(iso):
        d = open(iso, "rb").read()
        line(d[0:16] == b"SEGADISCSYSTEM  ", "boot sector disc id",
             repr(d[0:16]))
        line(d[0x1F0:0x200].startswith(b"JUE"), "region field", repr(d[0x1F0:0x200]))
        line(d[16 * 2048:16 * 2048 + 1] == b"\x01", "ISO9660 PVD present")
        for name in (b"IPX.MMD", b"GAME.MMD", b"STAGE1.MMD", b"SPX.SMD"):
            line(d.find(name) >= 0, "ISO contains %s" % name.decode())

    print("== 5. Final disc with the original soundtrack ==")
    if os.path.isfile("dist/valis3_mcd.cue"):
        cue = open("dist/valis3_mcd.cue").read()
        ntracks = cue.count("    INDEX 01")
        line(ntracks >= 55, "dist/valis3_mcd.cue with %d tracks" % ntracks)
        line("TRACK 01 MODE1/2048" in cue, "data track is MODE1/2048")
        man = json.load(open("dist/valis3_mcd.json")) if os.path.isfile("dist/valis3_mcd.json") else {}
        line(len(man.get("audio_tracks", [])) == 54,
             "track manifest maps %d disc tracks to the original PCE tracks"
             % len(man.get("audio_tracks", [])))
        tot = sum(t["seconds"] for t in man.get("audio_tracks", []))
        line(tot > 2400, "total original music on the disc", "%.1f min" % (tot / 60))


if __name__ == "__main__":
    main()
