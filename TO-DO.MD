# Star Wars: Demolition Recompilation TODO

Measurements come from `tools\recompone-demolition\fixtures\gameplay_desert.inputs`
at the `gameplay_settled` stage, 1920x1080, Enhanced preset, unless stated
otherwise. Frame pacing sits at 50-55 deadline misses per 60 frames throughout;
none of the work below moved it outside that band.

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

3. The frontend loses its 3D layer after a match. Jabba's palace, the character
   model and the arena globe are absent against black while the 2D layer draws
   normally, and it comes back on the next screen.
   `_retiredGameplayRenderFence` in `V82Compat` is raised when the shell takes
   back over and is cleared only from a selector draw callback; the main menu
   is not one of those, so the fence stays up until you advance a screen. Clear
   it when the shell takes over rather than from the selector callbacks.

4. The 3D Jabba's Palace frontend still renders at 4:3. Implemented behind
   `RECOMPONE_DEMOLITION_WIDE_FRONTEND=1`, off by default. The scene widens
   correctly and reveals two Bith musicians that 4:3 crops entirely, but the
   shell alternates two display buffers, one of which is incomplete, and
   `holdCompletedDemolitionFrontendFrame` re-presents the completed one.
   Widening changes the size that hold compares against. The flag suppresses
   the hold while a selector is widened, which is unverified.

5. The HUD warning banner tears - reopened, because the fix is unconfirmed.
   The anchor sent the right-hand corner widget to the right margin on screen
   position alone, splitting the band at 40% of the window. Any element drawn
   as several tiles across that split has some tiles sent to one edge and the
   rest to the other, which is what cut the banner in half. The corner test
   now also requires a plate-sized textured tile (40x40 or larger) or an
   untextured one, so a strip of small tiles cannot qualify. The corner
   widgets are confirmed not to move (radar centroid 335.7 -> 336.1, ring
   1563.1 -> 1562.9) but the banner itself has never been on screen for a
   capture. Its tiles are also unmeasured: searching the executable and the
   shared archives turns up no "warning" or "shield" string, so it is most
   likely pre-drawn artwork rather than text, and its tile sizes want
   checking against the 40x40 threshold once it can be seen.

   Putting it there from a script is half solved. The existing defeat
   injection is V8:2's and does not apply - `_playerVehicle` is only set from
   `TraceVehicleCreateRequest`, which Demolition never reaches - but the
   player is findable without it. `RECOMPONE_TRACE_DEMOLITION_OBJECTS=1`
   dumps every live object at render time, and exactly one carries a
   current/maximum pair of halfwords at +0x1C reading 1000/1000 while the
   rest read zero. `RECOMPONE_DEMOLITION_HOLD_SHIELDS_FRAME=<tick>` uses that
   to pin the player's shields at an eighth of capacity from the given
   gameplay tick.

   That is not enough on its own. Shields held at 125/1000 deplete the damage
   ring exactly as they should, and the banner still never appears, so it is
   raised by a damage event rather than by a threshold the HUD tests each
   frame. Nine thousand polls of the drive fixture with shields pinned drew
   no HUD tile the band does not always carry - the same 52x51 radar, 60x53
   ring and untextured blips and arc - so no opponent landed a hit either.
   What is left is Demolition's damage entry point, the equivalent of V8:2's
   func_80039DCC, called with the full-destroy flag clear.

   That same trace is also the strongest evidence the fix is sound: across a
   long run the only textured tiles the band ever carries are the 52x51 radar
   and the 60x53 ring, both comfortably over the 40x40 the corner test now
   demands, so nothing legitimate lost its anchor and the banner - whatever
   its tiles are - cannot be split across the two edges.

6. Buildings disappear in dense arenas. Suspected
   `RECOMPONE_DEMOLITION_DRAW_BUDGET`, which defaults to 64. Untested; it needs
   a measured frame cost before the default moves.

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
