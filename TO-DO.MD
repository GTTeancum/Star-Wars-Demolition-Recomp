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
     the near left, and only at the spawn camera - driving into the settlement
     and looking around shows clean, fully covered edges. Measured and ruled
     out, each a no-op on the hole area: row-cell padding at 16, omnidirectional
     traversal, headroom at 24/48/120, and falling back to the unclamped
     projection for NCLIP on triangles the +/-1024 clamp damages (87 triangles
     per frame took that path and not one pixel changed).
   - OPEN: skybox seams not yet investigated.
   - OPEN: 3D Jabba's Palace frontend still renders at 4:3. Not started.

3. The 2D overlay layer does not draw during gameplay. Neither the HUD (radar,
   armour/health, weapon panel) nor the pause, objectives and quit-confirmation
   overlays appear, although the world behind them freezes correctly and the
   game does reach those states.
   - This is upstream of the renderer, not a renderer bug: the software oracle
     (`RECOMPONE_ORIGINAL_RENDERER_ORACLE=1` with
     `RECOMPONE_GRAPHICS_PRESET=Original`) drops them identically.
   - `RECOMPONE_TRACE_HUD=1` shows what the engine actually submits where the
     HUD belongs: untextured 1x1 and 2x2 rectangles, no panels and no art. So
     the HUD build path is not running, rather than being drawn and lost.
   - `RECOMPONE_TRACE_MODAL_RECTS=1` does show 700 modal glyph rectangles per
     pause, so the pause text is built and reaches the renderer. Those two
     findings disagree and need reconciling; start there.
   - Reproduce with `tools\recompone-demolition\fixtures\return.inputs`-style
     input: reach `gameplay_settled`, press START, then capture a burst on the
     `pause_menu` stage.
   - Not reproduced: a report of the SELECT ARENA screen rendering black behind
     its text. A cold-boot replay of that screen, 260 frames of cycling the
     selector, and backing out and returning all render it correctly, so the
     path that produces it is still unknown.

4. WISHLIST: Add texture-pack support using textures sourced from the Dreamcast
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
