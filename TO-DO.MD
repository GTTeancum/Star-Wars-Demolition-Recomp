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

## Open

1. Far terrain is untextured beyond roughly 6000 camera units. The fog fade now
   carries it and it reads correctly, but the Dreamcast draws that range
   textured. The cell textures are already tagged by the coarse and transition
   hooks; what is missing is a Demolition-specific quad reconstruction. V8:2's
   cannot be reused - it pairs quad halves at a fixed 0x1C packet stride and
   folds the far arena into floating ribbons.

2. Fog falloff is approximated. The shader uses a fixed density of 0.275390625
   against a reconstructed PVR table. The real values are in the Dreamcast
   executable: density at `0x8C1B40A0`, and the 128-entry `FOG_TABLE` at PVR
   offset 0x200. Reading those would match the curve exactly rather than
   approximately.

3. The 3D Jabba's Palace frontend still renders at 4:3. Not started.

4. Skybox seams. Not investigated.

5. About 200 pixels of backdrop still show through the right gameplay margin,
   and 17 through the left. Small enough that the remaining cause has not been
   identified.

6. Not reproduced: a report of the SELECT ARENA screen rendering black behind
   its text. A cold-boot replay of that screen, 260 frames of cycling the
   selector, and backing out and returning all render it correctly. The path
   that produces it is still unknown, and the unmapped-call crash fixed above is
   a plausible but unconfirmed explanation.

7. The targeting reticle may sit slightly off its target. Pre-existing and
   unverified - it was left on exactly the treatment it had before the HUD
   anchoring change, so it is not a regression from that work.

8. WISHLIST: texture-pack support using Dreamcast textures. The loader exists
   and looks for `game\textures\2x`; every run reports 0% coverage because no
   pack has been produced. The disc is now readable via
   `tools\recompone-demolition\dreamcast\gdi.py`.

## Notes

- `tools\recompone-demolition\fixtures\README.md` explains the deterministic
  replays used for every measurement here.
- Levers measured against the gameplay edge and found to change nothing, so they
  need not be tried again: row-cell padding at 16, omnidirectional traversal,
  clip headroom at 0/24/48/120, terrain wide-fit, lateral and polygon padding,
  and an unclamped-projection NCLIP fallback. Several of these looked like they
  helped before the double-margin bug was found; they did not.
- Two analysis scripts cited in code comments (`analyze_object_pops.py`,
  `analyze_terrain_flicker.py`) live in the sibling Vigilante 8: 2nd Offense
  project and are not on this machine.
