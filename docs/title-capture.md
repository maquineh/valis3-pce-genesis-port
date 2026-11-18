# PC Engine title captures

`states/title_pce_menu.mednafen` and `states/title_pce_menu.bmp` capture the
original Japanese disc using the Beetle PCE Fast libretro core at frame 900,
after RUN was held on frames 180–194. They show the START/CONTINUE menu.

`states/title_pce_logo.mednafen` and `states/title_pce_logo.bmp` capture the
same disc and core at frame 18900. RUN was held on frames 120–124 to pass the
system screen, and 400–404 to select START. The opening plays, followed by
the original Japanese VALIS III logo and copyright. The BMP is the frame
rendered by the core and the raw MDFNSVST state was serialized at the same
frame. Both BMPs are 256x243 and their SHA-256 hashes are recorded in
`game/res/gfx/title.json`.

The port's title is a composition of these two source frames: the logo and
copyright retain their original coordinates; the PUSH RUN BUTTON prompt is
removed and the original menu is shifted down 88 pixels between the logo and
copyright. The lower 19 lines are cropped for the Mega Drive 224-line display.
This combines two separate original screens; the composition is not a claim
that the source game displayed the menu on the logo screen.

`tools/pack_title_capture.py` composites the pixels into background tiles,
reserves transparent tile 0, quantizes RGB to three bits per channel, and
allocates tiles to four 16-entry palette lines. The generated image uses 353
unique tiles and two palette lines with 16 and 10 entries. Quantization changes
8,348 pixels, with mean absolute channel error 0.164266 and maximum channel
error 4/255. `tools/test_title_capture.py` reconstructs and validates the
actual assets. Both scripts require Pillow:

```powershell
py -3 tools/pack_title_capture.py
py -3 tools/test_title_capture.py
```

The original sword cursor is drawn dynamically, with UP/DOWN selecting START
or CONTINUE. LEFT/RIGHT selects a prototype scene while START is highlighted;
START or A/B/C confirms. Returning from a scene with START saves its player
position in dedicated BRAM files; CONTINUE restores that scene and position.
Enemy state and completed-stage progress are not saved yet. See
`stage-status.md` for the selector and failure behavior.
