# Star Wars: Demolition Recompilation TODO

## Playability blockers

- [ ] Fix the memory-card save freeze.
  - Reproduce by starting a save from the frontend with both an existing card and a newly created card.
  - Ensure the save operation returns to the menu, persists valid card data, and does not stall the emulated CPU or host frame loop.
- [ ] Repair frontend/menu rendering.
  - Keep fullscreen FMV, background, menu, and other 2D packets in authored screen space.
  - Remove the collapsing trapezoid/perspective distortion without regressing enhanced gameplay rendering.

## Rendering

- [ ] Finish and validate FXAA.
  - Apply it consistently to the final enhanced-renderer output without blurring or damaging HUD and menu text.
- [ ] Remove dithering completely.
  - Remove PS1 dithering from rendering behavior, configuration, menus, environment overrides, and shader/runtime branches.
- [ ] Fix affine texture projection.
  - Preserve the game's authored affine texture coordinates where projective metadata is absent or unreliable.
  - Correct terrain and frontend texture mapping without introducing seams, warping, or incorrect mip selection.
- [ ] Finish Demolition-specific terrain rendering.
  - Match native terrain texture detail and ordering while retaining the corrected continuous terrain geometry.
- [ ] Increase world-object visibility and draw range while maintaining playable frame pacing.

## Verification

- [ ] Run deterministic full-size capture comparisons for frontend, vehicle selection, arena selection, gameplay, pause, results, and memory-card flows.
- [ ] Complete a sustained loose-file gameplay soak with saving, loading, combat, pause/resume, and return-to-menu coverage.

## Distribution

- [ ] Produce a single self-contained executable.
  - Bundle all managed and native DLL dependencies into `StarWarsDemolitionPC.exe`.
  - Keep the game's loose media/data files external beside the executable.
  - Verify it runs on a clean Windows machine without a separately installed .NET runtime or loose dependency DLLs.
