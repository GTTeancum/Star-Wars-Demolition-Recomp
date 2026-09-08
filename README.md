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

This is intentionally a playability build, not a fidelity-complete port.

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
- The frontend and HUD keep their native 4:3 layout; full terrain fidelity and
  longer-range world visibility remain tracked separately from widescreen edge
  coverage.

Generated C#, build products, captures, and retail media remain local and are
not tracked.
