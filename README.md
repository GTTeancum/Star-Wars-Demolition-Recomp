# Star Wars: Demolition PC recompilation

This is a playable-first static recompilation of the USA PlayStation release
(`SLUS-01183`) using RecompOne and the proven Vigilante 8 runtime. It runs from
loose files only: no CUE or BIN is opened by the finished executable.

## Playable milestone

- Boots the retail shell, menus, loading screens, and Desert level from loose
  files.
- Loads 23 relocatable level and vehicle overlays.
- Runs native match logic, collision, camera updates, HUD, controller input,
  weapons, pause handling, XA streams, and CD music.
- Runs the retail terrain scan converter and submits its complete 4096-bucket
  world ordering table to the host GPU.
- Draws textured arena terrain, the selected vehicle, opponents, and a bounded
  set of nearby props at gameplay speed.
- Adds a gameplay-only 16:9 view with widened terrain and object visibility,
  perspective-correct textures, true-colour output without dithering, and
  HUD-safe FXAA while preserving the authored 4:3 frontend.
- Draws every arena's ground textures and all eight loading screens from the
  Dreamcast release, built from that disc by the tools below.

This is intentionally a playability build, not a fidelity-complete port.

## Current handoff status

- The repository is set up to work from `D:\Programming\GitHub\Star-Wars-Demolition-Recomp`.
- The finished runtime is a loose-file build: `game\StarWarsDemolitionPC.exe`
  loads data from the prepared `game` directory and does not open the CUE/BIN
  at runtime.
- The latest playable-flow validation covered frontend navigation, memory-card
  access with a fresh blank card, mission loading, gameplay, combat, pause,
  quit confirmation, and return to the frontend.
- Memory-card writes no longer freeze in the tested flow; the local prepared
  data includes a fresh `carda.sav`, with previous test/back-up cards kept
  beside it for local reference.
- Completed quality-of-life video work includes FXAA, disabled dithering,
  perspective-correct texture output, a gameplay widescreen option, and the
  single-executable publish path.
- Two settings go beyond the original hardware and are on outside the
  `original` graphics preset: `SoftHorizon` spreads the distance fade across
  the mid distance rather than the narrow band the PowerVR fog table gives it,
  and `GradientSmoothing` rebuilds the colour levels a small palette never
  had. Both are described in `TO-DO.MD`.
- The remaining work is tracked in `TO-DO.MD`; keep that file as the short,
  numbered source of truth and remove items as they are completed.

## Prepare the loose files

The CUE is used once, by the preparation tool. It creates `game` with the ISO
files, raw 2336-byte STR/XA sector streams, CD-audio OGG files, and the loose
manifest required by the runtime.

```powershell
python tools\recompone-demolition\prepare_loose_media.py `
  --cue "D:\path\to\Star Wars - Demolition (USA).cue" `
  --manifest tools\recompone-reference\RecompOne.Runtime\Cdrom\DemolitionLooseManifest.json `
  --loose-root game
```

Retail data under `game` is user-supplied and ignored by Git.

## Build the texture pack

The pack is derived from a Dreamcast copy of the game and lands in
`game\mods\enhanced_textures_2x`, which is outside the repository along with
the rest of the retail data - so it does not survive a fresh clone and has to
be regenerated. Point `extract_textures.py` at a Dreamcast disc image first;
`tools\recompone-demolition\dreamcast\README.md` covers that side.

```powershell
python tools\recompone-demolition\dreamcast\extract_textures.py

python tools\recompone-demolition\texturepack\build_terrain_atlases.py

python tools\recompone-demolition\dreamcast\build_loading_cards.py
```

Without it the runtime reports `no replacement pack found` and draws the
original textures, which is a supported state rather than a failure.

## Generate and publish

```powershell
python tools\recompone-demolition\prepare_reference.py

dotnet run --project tools\recompone-reference\RecompOne.Recompiler `
  -- reference\demolition.recompone.json

python tools\recompone-demolition\publish_loose.py
```

The publisher places one self-contained `StarWarsDemolitionPC.exe` directly in
`game`; managed and native runtime dependencies are bundled, so no separate
.NET runtime or sidecar DLLs are required. Retail game data remains external as
loose files. Launch it without arguments:

```powershell
game\StarWarsDemolitionPC.exe
```

For development, the generated host can instead receive any complete prepared
loose directory:

```powershell
dotnet run --project reference\generated\StarWarsDemolitionPC.csproj `
  -- game
```

## Current tradeoffs

- Visibility defaults to 64 nearby objects per frame, covering the complete
  measured Tatooine spawn set. Set `RECOMPONE_DEMOLITION_DRAW_BUDGET` from 1
  through 4096 to trade speed for scene density in unusually busy arenas.
- Ordinary 2D frontend and HUD layouts keep their native 4:3 framing. Gameplay
  widescreen is active, but edge coverage and the 3D Jabba's Palace frontend
  still need dedicated widescreen work.
- The texture pack covers the ground and the loading screens. About 71% of
  texture lookups are still the original art - vehicles, buildings and HUD -
  because those load as raw VRAM uploads rather than as identifiable images in
  the archives. `RECOMPONE_VRAM_UPLOAD_DUMP_DIR` records them for that work.
- Full terrain fidelity and longer-range world visibility remain open in
  `TO-DO.MD`.

Generated C#, build products, captures, and retail media remain local and are
not tracked.
