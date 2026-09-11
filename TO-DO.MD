# Star Wars: Demolition Recompilation TODO

Measurements below come from `tools\recompone-demolition\fixtures\gameplay_desert.inputs`
at the `gameplay_settled` stage, 1920x1080, Enhanced preset.

1. Finish terrain fidelity and increase world-object visibility and draw range
   while maintaining playable frame pacing.
   - DONE: far terrain no longer draws as a black silhouette. Past roughly 6000
     camera units the engine emits untextured terrain whose vertex RGB is the
     authored lighting index in grayscale; that index is now modulated by the
     cell's average texture colour. Far-bucket luminance 66 -> 125.
   - OPEN: distant scenery models still render near-black (the mesa silhouettes
     along the horizon are world objects, not terrain - confirmed with
     `RECOMPONE_V82_DEBUG_TERRAIN_COVERAGE=1`, which leaves them untinted).
     Decide first whether they are authored sunset silhouettes; that needs
     retail PS1 ground truth, which this machine does not have.
   - OPEN: object draw budget still defaults to 64.
     `RECOMPONE_V82_TERRAIN_RANGE_SCALE` does not extend terrain and only adds
     an occasional distant vehicle, so draw range needs a different lever.
   - OPEN: rebuild the coarse-terrain quad reconstruction for Demolition.
     Routing its packets through V8:2's path folds the arena into floating
     ribbons because that path pairs quad halves at a fixed 0x1C stride.
     Doing it properly would texture far terrain rather than flat-tint it.

2. Fix gameplay widescreen edge coverage, including missing terrain and world
   geometry and skybox seams, and expand the 3D Jabba's Palace frontend while
   keeping ordinary 2D UI at its authored aspect ratio.
   - DONE: the terrain scan converter now runs with a 16:9 frustum. Its
     per-cell visibility test read the authored 4:3 camera width; hooking
     ExpandTerrainFrustum around 0x8001CC78 raised submitted cells 714 -> 872
     and emitted cells 473 -> 586.
   - DONE: widescreen clip headroom is 0 for Demolition rather than V8:2's 48.
     The extra packed-SX compression pushed dense terrain polygons under the
     NCLIP rounding cliff and culled them as backfacing.
   - Together those cut backdrop visible through missing terrain from 57,446
     pixels to 36,292, with frame pacing unchanged.
   - OPEN: about 36,000 pixels of edge holes remain, concentrated in a wedge at
     the near left. `satX` (packed X beyond the representable +/-1023) rises
     from 303 to 415 with the wider walk, so the remaining loss is most likely
     near off-axis vertices saturating the packed projection. Row padding,
     omnidirectional traversal and larger headroom were each measured and
     change nothing.
   - OPEN: skybox seams not yet investigated.
   - OPEN: 3D Jabba's Palace frontend still renders at 4:3. Not started.

3. WISHLIST: Add texture-pack support using textures sourced from the Dreamcast
   version. The loader already exists and looks for `game\textures\2x`; every
   run reports 0% coverage because no pack has been produced.

## Notes for whoever picks this up

- `tools\recompone-demolition\fixtures\README.md` explains the deterministic
  replay used for every measurement above.
- Two analysis scripts referenced in code comments
  (`analyze_object_pops.py`, `analyze_terrain_flicker.py`) live in the sibling
  Vigilante 8: 2nd Offense project and are not on this machine, so the
  pop-in and terrain-flicker numbers quoted in those comments cannot currently
  be reproduced or extended.
