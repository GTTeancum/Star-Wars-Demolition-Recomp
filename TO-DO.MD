# Star Wars: Demolition Recompilation TODO

Measurements come from `tools\recompone-demolition\fixtures\gameplay_desert.inputs`
at the `gameplay_settled` stage, 1920x1080, Enhanced preset, unless stated
otherwise. Frame pacing sits at 50-55 deadline misses per 60 frames throughout;
none of the work below moved it outside that band.

## Done

1. Widescreen framing. `V()` added the target margin to the packed screen X and
   the recovered projection centre, and the vertex shader added it again through
   `uPosBias`, so the whole 3D view sat one margin (54 native pixels at 16:9)
   right of centre. Craft centre 62.6% of frame width -> 49.9%. This was also
   the cause of the torn gameplay edge: backdrop visible through the left margin
   fell from 57,446 pixels to 17, and the right margin sits at 202.

2. The horizon. Distant terrain drew as a black band because the Dreamcast table
   fog mixes toward the arena's COLS colour and that colour was read from V8:2's
   `gp+0xDA4`; Demolition's block is shifted, the read returned zero, and every
   distant surface faded to black. Now read from `gp+0xCF0`, confirmed against
   the Dreamcast executable - see `tools\recompone-demolition\dreamcast`.

3. The terrain scan converter now runs with a 16:9 frustum
   (`ExpandTerrainFrustum` around 0x8001CC78). Emitted terrain cells 473 -> 587.
   Without it the right margin loses 535 pixels to backdrop rather than 202.

4. The 2D overlay layer. Nothing drew - no radar, armour ring or reticle, and
   pausing froze the world with no menu on it. The post-hook on 0x80035930 was
   submitting the world ordering table as soon as the world renderer returned,
   but the engine keeps adding the HUD and the modal overlays to that same table
   afterwards, so everything added later was never submitted. The native
   end-of-frame submission already draws the complete table.

5. Four indirect call targets were resolved to literals but never recompiled, so
   the run died with "unmapped call" the first time each was reached - one in
   the model renderer on the pause-to-quit route, two in the shell overlays that
   own the frontend. Iterated to a fixed point.

6. Demolition's right-hand HUD widget anchors to the right margin instead of
   being dragged inboard with the radar.

7. Fog falloff. The shader's density was V8:2's 0.275390625; Demolition's
   installer at 0x8C058A20 passes 0.252f, which the PVR register's 8.8 encoding
   truncates to 0.251953125. It is passed as `uFogDensity` now. Demolition never
   writes the 128-entry `FOG_TABLE` - every call to the register helper at
   0x8C0CCA28 uses an offset below 0x200 - so the reconstructed table needs no
   per-game variant.

8. Arena ground textures come from the Dreamcast now. Terrain resolves to
   Dreamcast art on 100% of lookups (37,376 of 37,376, no misses); overall
   texture coverage went from 0% to 29%. Both versions store the set the same
   way, as an eight-bit image and its palette in the `XBMP` chunk of the .EXP -
   the PlayStation as one sheet of 48-pixel cells, the Dreamcast as one 64x64
   texture per cell - and the counts agree exactly for all eight arenas.
   Correlation pairs them row-major, the intended cell scoring above 0.97
   against a rival below 0.75. Ten Death Star cells keep the original art:
   they carry real structure and still disagree with the texture that would
   land on them, which is art the later version redrew. Built by
   `tools\recompone-demolition\texturepack\build_terrain_atlases.py`.

9. Loading screens come from the Dreamcast. The overlay existed but was gated
   on the title being Vigilante 8, and keyed on a signal that describes only
   the closing frame here; Demolition draws the screen from the `SHELL_LOAD`
   overlay, which stays resident into the match, so the gameplay flag is what
   closes the window. The Dreamcast picture is the PlayStation band at exactly
   2x, which lets a difference key preserve the engine-drawn arena title over
   the replaced art instead of holding back a strip of the original.

## Open

1. The rest of the texture pack. 29% of lookups are covered; the remainder is
   vehicles, buildings, sky and HUD art. The dump of resolved textures is the
   wrong unit to work from - it produces 29,907 per-primitive UV windows, most
   of them under 256 pixels, some as small as 3x6. The upload is the right
   unit: `RECOMPONE_VRAM_UPLOAD_DUMP_DIR` writes one file per distinct image
   the game sends to VRAM, 1,055 of them carrying an image rather than a colour
   table in a Desert run, and `RECOMPONE_TRACE_FONT_FILE_SOURCES=1` names the
   disc file behind each. What is missing is a runtime path that resolves a
   sampling window back to the upload covering it; `FontFileProvenance` already
   does exactly that for .FNT files and would generalise.

2. Fonts. They cannot be direct file replacements: the layouts differ. The
   PlayStation .FNT format is reversed - a table of five-byte records from
   offset 18 (u16 pixel offset into a 256-wide strip, width, height, kern)
   followed by a standard TIM - and the boxes it gives land exactly on the
   glyphs. The Dreamcast sheets hold the same glyph inventory in the same order
   but wrap differently, and they cannot be segmented by gaps: the italic faces
   touch, so a 119-glyph sheet comes apart into 39 runs. Matching each
   PlayStation glyph into the Dreamcast sheet by shape is the way through.
   The inventories are not one-to-one at sheet level either - the PlayStation
   GAME.FNT merges the symbol block of one Dreamcast sheet with the accented
   block of another.

3. Far terrain is untextured beyond roughly 6000 camera units - textured
   coverage by depth is 100% to 4000, 55% to 6000 and 0% past it. The fog fade
   carries it and it reads correctly now, but the Dreamcast draws that range
   textured.

   Three things previously recorded as blockers are not. The pairing stride is
   0x1C, identical to V8:2, measured over 19 consecutive pairs. Both writers do
   tag their cells - the route writer at 0x8002ABEC contributes about 10,000
   tags a frame, and an earlier note claiming it never tagged came from a
   40-sample trace that was simply too early. And the terrain CLUT, which was
   read from V8:2's gp+0xDA8 and returned 0x0001, now reads correctly from
   gp+0xCF4.

   What remains is the vertex ordering inside each half. With everything above
   corrected, 79% of halves pair and the rebuilt quads still come out twisted,
   so the far arena grows triangular shards and a checkerboard. Compare
   Demolition's route and detail writers against V8:2's for the order the three
   vertices of each half are written in.

4. The frontend loses its 3D layer after a match. Jabba's palace, the character
   model and the arena globe are absent against black while the 2D layer draws
   normally, and it comes back on the next screen.
   `_retiredGameplayRenderFence` in `V82Compat` is raised when the shell takes
   back over and is cleared only from a selector draw callback; the main menu
   is not one of those, so the fence stays up until you advance a screen. Clear
   it when the shell takes over rather than from the selector callbacks.

5. The 3D Jabba's Palace frontend still renders at 4:3. Implemented behind
   `RECOMPONE_DEMOLITION_WIDE_FRONTEND=1`, off by default. The scene widens
   correctly and reveals two Bith musicians that 4:3 crops entirely, but the
   shell alternates two display buffers, one of which is incomplete, and
   `holdCompletedDemolitionFrontendFrame` re-presents the completed one.
   Widening changes the size that hold compares against. The flag suppresses
   the hold while a selector is widened, which is unverified.

6. The HUD warning banner tears. Anchoring the right-hand widget to the right
   margin keys on screen position, and the banner shares its rows with the
   damage ring, so "Warning Shields Low" is cut in half. Key the anchor on
   texture page instead of position.

7. Buildings disappear in dense arenas. Suspected
   `RECOMPONE_DEMOLITION_DRAW_BUDGET`, which defaults to 64. Untested; it needs
   a measured frame cost before the default moves.

8. Fading between screens is coarse and banded. Worth reverse engineering the
   Dreamcast's version.

9. Skybox seams. Not investigated.

10. About 200 pixels of backdrop still show through the right gameplay margin,
    and 17 through the left. The PVR fog clamp registers are also still
    unmodelled; they come from a per-render-state struct at +0x88 and +0x8C
    rather than constants.

11. The targeting reticle may sit slightly off its target. Pre-existing and
    unverified.

## Notes

- `tools\recompone-demolition\fixtures\README.md` explains the deterministic
  replays used for every measurement here.
- The texture pack is generated into `game\mods\enhanced_textures_2x`, which is
  outside the repository because it is derived from the user's own discs. Run
  `texturepack\build_terrain_atlases.py` and `dreamcast\build_loading_cards.py`
  to rebuild it.
- A manifest that fails to parse throws from inside the GL load callback, and
  the host used to report that as "window unavailable" and carry on headless,
  so the pack silently did nothing. That message now carries the exception type
  and stack.
- Levers measured against the gameplay edge and found to change nothing, so they
  need not be tried again: row-cell padding at 16, omnidirectional traversal,
  clip headroom at 0/24/48/120, terrain wide-fit, lateral and polygon padding,
  and an unclamped-projection NCLIP fallback. Several of these looked like they
  helped before the double-margin bug was found; they did not.
- Two analysis scripts cited in code comments (`analyze_object_pops.py`,
  `analyze_terrain_flicker.py`) live in the sibling Vigilante 8: 2nd Offense
  project and are not on this machine.
