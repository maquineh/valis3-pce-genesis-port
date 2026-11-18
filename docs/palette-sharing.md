# Sharing the four Mega Drive palette lines

The Mega Drive has four 16-color palette lines shared between backgrounds and
sprites. Color index 0 is transparent in sprites. The placeholder player uses
line 3, indices 8, 9 and 15; these are CRAM entries 56, 57 and 63. The seven
captured scene maps do not use those indices on line 3, so setting the player
colors there leaves their visible background pixels unchanged.

Stage 2C uses eight PCE palette IDs in its captured BAT, so choosing four
palettes and sending the others to a fallback changes the HUD colors. Its
resources use `--pack-all-palettes`: the packer groups source palettes by
their used colors, remaps tile pixels, and duplicates tiles when one source
tile appears with different PCE palettes. The output retains every captured
pixel color in four MD lines. The Stage 2C pack has 159 tile/palette variants;
indices 8, 9, and 15 on line 3 remain free for sprites. Regenerate and verify
it with:

```powershell
py -3 tools/pack_state_window.py "states\Valis III (Japan).dad575d3e6e26b145cc260e5858b8c48.mc2" stage2c_state 0 8 16 24 --palette-order 2,3,0,14 --reserve-line3 8,9,15 --pack-all-palettes
py -3 tools/pack_state_window.py "Valis III (Japan).dad575d3e6e26b145cc260e5858b8c48.mc3" stage2c_b_state 34 --columns 32 --reserve-line3 8,9,15 --pack-all-palettes
py -3 tools/pack_state_window.py states/stg3a_additional.mc4 stage3a_state 32 32 --columns 0,32 --palette-order 2,1,0,2 --reserve-line3 8,9,15 --pack-all-palettes
py -3 tools/gen_player_spr.py
py -3 tools/test_stage_palette.py
py -3 tools/test_stage2c_palette.py
```

The Stage 3A capture packs BAT row 32 from columns 0 and 32 as adjacent
horizontal screens. `--columns` selects a different BAT start column for each
screen while retaining the older shared-column syntax.

`--palette-order` must be a permutation of the four most-used PCE palettes; in
exact-color mode it guides preferred line assignments while the packer groups
all used palettes.
`--reserve-line3` aborts before writing resources if a listed index appears in
the generated line-3 background tiles. The tests independently inspect all
seven scenes, check that the sprite uses exactly those reserved indices, and
compare nontransparent stage pixels before and after the reordering. Future
scenes need the same check; the shared sprite slots are not universally free.
