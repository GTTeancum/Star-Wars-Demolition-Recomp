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

## Open

1. Far terrain is untextured beyond roughly 6000 camera units - textured
   coverage by depth is 100% to 4000, 55% to 6000 and 0% past it. The fog fade
   carries it and it reads correctly now, but the Dreamcast draws that range
   textured.

   Three things previously recorded as blockers are not. The pairing stride is
   0x1C, identical to V8:2, measured over 19 consecutive pairs. Both writers do
   tag their cells - the route writer at 0x8002ABEC contributes about 10,000
   tags a frame, and an earlier note claiming it never tagged came from a
   40-sample trace that was simply too early. And the terrain CLUT, which was
   read from V8:2's gp+0xDA8 and returned 0x0001, now reads correctly from
   gp+0xCF4; that was what turned the first trial green.

   What remains is the vertex ordering inside each half. With everything above
   corrected, 79% of halves pair and the rebuilt quads still come out twisted,
   so the far arena grows triangular shards and a checkerboard. Compare
   Demolition's route and detail writers against V8:2's for the order the three
   vertices of each half are written in.

2. The frontend selectors intermittently lose their entire 3D layer. Observed
   live on CHOOSE CONTESTANT and earlier on SELECT ARENA: the title, the stat
   bars, the contestant and vehicle names and the button prompts all draw
   normally, and the Jabba's palace room, the character model and the arena
   globe are simply absent against black. The window keeps running at 59.9 FPS,
   so it is not a hang.

   Not reproduced from a script. Ruled out so far: the run never trips the
   `_retiredGameplayRenderFence` or `IsCurrentOverlayMemory` guards in
   `DrawDemolitionVisibilityLeaf`, which were the obvious suspects since the 2D
   layer draws through a different path; a cold-boot replay of both selectors,
   260 frames of cycling the arena selector, backing out and returning, and
   accepting each selector 12 polls after it appears so the next screen is
   entered mid-teardown, all render correctly. Something about interactive
   timing is the trigger, so the next step is capturing the input timing of a
   failing run rather than more scripted variants.

3. The 3D Jabba's Palace frontend still renders at 4:3. Implemented behind
   `RECOMPONE_DEMOLITION_WIDE_FRONTEND=1`, off by default.

   The scene widens correctly with it on and the room reveals two Bith musicians
   that 4:3 crops entirely. What is not settled is the shell's two-buffer
   present: it alternates display buffers, one of which is incomplete, and
   `holdCompletedDemolitionFrontendFrame` re-presents the completed one.
   Widening changes the size that hold compares against, so the first attempt
   held the wrong buffer and lost the whole 2D layer. The flag now also
   suppresses that hold while a selector is widened, which is the obvious
   pairing but is unverified - it needs checking against the two-buffer
   behaviour before the flag can default on. It may well share a cause with
   item 2 above.

4. Skybox seams. Not investigated.

5. About 200 pixels of backdrop still show through the right gameplay margin,
   and 17 through the left. Small enough that the remaining cause has not been
   identified. The PVR fog clamp registers are also still unmodelled; they come
   from a per-render-state struct at +0x88 and +0x8C rather than constants.

6. The targeting reticle may sit slightly off its target. Pre-existing and
   unverified - it was left on exactly the treatment it had before the HUD
   anchoring change, so it is not a regression from that work.

7. WISHLIST: texture-pack support using Dreamcast textures. The loader exists
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
