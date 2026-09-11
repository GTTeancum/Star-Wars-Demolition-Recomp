# Deterministic replay fixtures

Scripted controller input for reproducible captures. Point the runtime at one
with `RECOMPONE_INPUT_FILE` and disable live input:

```powershell
$env:RECOMPONE_INPUT_FILE =
  "D:\Programming\GitHub\Star-Wars-Demolition-Recomp\tools\recompone-demolition\fixtures\gameplay_desert.inputs"
$env:RECOMPONE_DISABLE_LIVE_INPUT = "1"
$env:RECOMPONE_SCRIPT_STAGE_CAPTURE_FILTER = "gameplay_settled"
$env:RECOMPONE_PRESENTATION_CAPTURE = "1"
$env:RECOMPONE_PRESENTATION_RESOLUTION = "1920x1080"
$env:RECOMPONE_SCRIPT_EXIT_AFTER_POLLS = "2720"
$env:RECOMPONE_CAPTURE_DIR = "D:\Programming\GitHub\Star-Wars-Demolition-Recomp\work\my-capture"
D:\Programming\GitHub\Star-Wars-Demolition-Recomp\game\StarWarsDemolitionPC.exe
```

`gameplay_desert.inputs` reaches settled Desert gameplay at about poll 2660.

Entries are `startPoll+duration=BUTTON`. A `[after:stage@visit]` header makes the
following entries relative to the poll at which the runtime signalled that
stage, so a fixture survives the load-time drift that makes absolute polls
fragile. Stage names come from `InputManager.SignalScriptStage` callers.

The route through the frontend depends on the memory card in `game`: with a
saved profile present the game goes straight from the main menu to the arena
selector, and with a blank card it stops at Player Profiles first. The latched
accept pulses in the main-menu block cover both.
