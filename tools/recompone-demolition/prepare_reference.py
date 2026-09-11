#!/usr/bin/env python3
"""Generate the initial Star Wars: Demolition RecompOne configuration.

The PS1 game uses the same 0x80100000 relocatable DLL format as Vigilante 8.
This bootstrap deliberately starts with RecompOne call discovery plus linear
sweep. Runtime evidence can add missed callback and jump-table entries later.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
DEFAULT_DISC_ROOT = REPO / "game"
DEFAULT_OUTPUT = REPO / "reference"
MAIN_EXE = "SLUS_011.83"

# Runtime-reached entry points that the bootstrap scan cannot infer from a
# conventional JAL edge (for example, tail calls and address-table callbacks).
EXTRA_MAIN_FUNCTIONS = [
    "0x80015A70",
    "0x80023AA0",
    "0x80023C5C",
    "0x80023C64",
    # All targets in the seven 16-way model primitive dispatch tables at
    # 0x80024B80..0x80024D3C.  They are reached through register-indirect
    # jumps, so RecompOne's ordinary call discovery cannot see them.
    "0x80023CCC",
    "0x80023D4C",
    "0x80023D80",
    "0x80023DFC",
    "0x80023E60",
    "0x80023EAC",
    "0x80023F50",
    "0x80023F6C",
    "0x80023FE8",
    "0x8002401C",
    "0x80024064",
    "0x80024080",
    "0x800240FC",
    "0x80024128",
    "0x80024188",
    "0x800241BC",
    "0x800241F0",
    "0x80024298",
    "0x80024328",
    "0x800243A4",
    "0x800243EC",
    "0x8002448C",
    "0x8002451C",
    "0x80024598",
    "0x800245C8",
    "0x80024680",
    "0x800246C0",
    "0x800246F8",
    "0x800247D0",
    "0x8002493C",
    "0x800249C0",
    "0x80024A0C",
    "0x80024B50",
    "0x80025B20",
    "0x80025B5C",
    "0x80025B8C",
    "0x80025E14",
    "0x80025E1C",
    "0x80025E24",
    "0x80025E34",
    "0x80025E3C",
    "0x80025E44",
    "0x80025E4C",
    "0x80025E54",
    "0x80025E6C",
    "0x80025E78",
    "0x80025EA0",
    "0x80025EAC",
    "0x80026904",
    "0x800424E0",
    "0x80042BC0",
    "0x8005A310",
]

EXTRA_OVERLAY_FUNCTIONS: dict[str, list[str]] = {
    "LEVELS_DAGOBAH": ["0x80100200"],
    "LEVELS_DETHSTAR": ["0x801003EC"],
    "SHARED_SWOOP": ["0x80100070"],
}

PROVEN_PATCHES = [
    {
        # Diagnostic/test marker for the profile gate before the requested 3D
        # frontend; it does not alter the native profile implementation.
        "overlay": "SHELL_SHELL",
        "address": "801062CC",
        "target": (
            "RecompOne.Runtime.Sdk.V82Compat."
            "TraceDemolitionProfileState"
        ),
        "mode": "pre",
    },
    {
        # Process-local marker for Demolition's native 3D contestant selector.
        "overlay": "SHELL_SHELL",
        "address": "8010A7CC",
        "target": (
            "RecompOne.Runtime.Sdk.V82Compat."
            "TraceDemolitionContestantState"
        ),
        "mode": "pre",
    },
    {
        # Native tournament opponent-selection screen reached after confirming
        # the player's contestant.
        "overlay": "SHELL_SHELL",
        "address": "801099CC",
        "target": (
            "RecompOne.Runtime.Sdk.V82Compat."
            "TraceDemolitionOpponentsState"
        ),
        "mode": "pre",
    },
    {
        # The contestant/arena accept path uses this small scripted transition
        # object.  Trace its animation handle and flags without replacing the
        # retail callback so stalled frontend transitions can be diagnosed.
        "overlay": "SHELL_SHELL",
        "address": "80105710",
        "target": (
            "RecompOne.Runtime.Sdk.V82Compat."
            "TraceDemolitionFrontendTransition"
        ),
        "mode": "pre",
    },
    {
        # Parent controller for the shell's arena/contestant sequence.  Its
        # state-5 child completion decides whether another selector is built
        # or the shell exits into gameplay.
        "overlay": "SHELL_SHELL",
        "address": "8010D298",
        "target": (
            "RecompOne.Runtime.Sdk.V82Compat."
            "TraceDemolitionFrontendController"
        ),
        "mode": "pre",
    },
    {
        "overlay": "SHELL_SHELL",
        "address": "8010D298",
        "target": (
            "RecompOne.Runtime.Sdk.V82Compat."
            "TraceDemolitionFrontendControllerExit"
        ),
        "mode": "post",
    },
    {
        "overlay": "SHELL_SHELL",
        "address": "8010D954",
        "target": (
            "RecompOne.Runtime.Sdk.V82Compat."
            "TraceDemolitionFrontendLoopExit"
        ),
        "mode": "post",
    },
    {
        "overlay": "SHELL_SHELL",
        "address": "8010DEF8",
        "target": (
            "RecompOne.Runtime.Sdk.V82Compat."
            "TraceDemolitionShellFrontendExit"
        ),
        "mode": "post",
    },
    {
        # Process-local marker for Demolition's native 3D arena selector.
        "overlay": "SHELL_SHELL",
        "address": "8010BE50",
        "target": (
            "RecompOne.Runtime.Sdk.V82Compat."
            "TraceDemolitionArenaState"
        ),
        "mode": "pre",
    },
    {
        # Demolition's native text renderer is the instruction-identical
        # counterpart of V8:2's 0x8001A3B0 routine.  Observe this seam so the
        # process-local menu harness can identify the 3D level/vehicle screens
        # from their own authored labels without replacing retail menu logic.
        "overlay": "main",
        "address": "8001AE2C",
        "target": (
            "RecompOne.Runtime.Sdk.V82Compat."
            "TraceNativeOptionsText"
        ),
        "mode": "pre",
    },
    {
        # The 3D frontend (profiles, contestant, and arena selectors) submits
        # its authored headings through this companion text renderer.
        "overlay": "main",
        "address": "8001B138",
        "target": (
            "RecompOne.Runtime.Sdk.V82Compat."
            "TraceNativeOptionsText"
        ),
        "mode": "pre",
    },
    {
        # Profile names, selector labels, and the editable profile-name body
        # use the variable-width companion rather than the heading renderer.
        "overlay": "main",
        "address": "8001B0D4",
        "target": (
            "RecompOne.Runtime.Sdk.V82Compat."
            "TraceNativeOptionsText"
        ),
        "mode": "pre",
    },
    {
        # Observe the packet object produced by that variable-width renderer;
        # this distinguishes missing glyph generation from a bad OT link.
        "overlay": "main",
        "address": "8001A344",
        "target": (
            "RecompOne.Runtime.Sdk.V82Compat."
            "TraceDemolitionTextObject"
        ),
        "mode": "post",
    },
    {
        # Arena/contestant selectors create their scene object through this
        # shared hierarchy factory; capture its returned object and fields.
        "overlay": "main",
        "address": "8002EDA8",
        "target": (
            "RecompOne.Runtime.Sdk.V82Compat."
            "TraceDemolitionModelCreate"
        ),
        "mode": "post",
    },
    {
        # Observe which deepest child receives the selector's state-10 accept
        # notification; this is diagnostic only and leaves hierarchy walking
        # to the retail routine.
        "overlay": "main",
        "address": "8002FAFC",
        "target": (
            "RecompOne.Runtime.Sdk.V82Compat."
            "TraceDemolitionSelectorAcceptTarget"
        ),
        "mode": "post",
    },
    {
        "overlay": "main",
        "address": "80023C5C",
        "target": (
            "RecompOne.Runtime.Sdk.V82Compat."
            "EnterDemolitionGeometry23C5C"
        ),
        "mode": "pre",
    },
    {
        "overlay": "main",
        "address": "80023C5C",
        "target": (
            "RecompOne.Runtime.Sdk.V82Compat."
            "LeaveDemolitionGeometryContinuation"
        ),
        "mode": "post",
    },
    {
        # Primitive handlers tail-dispatch back here for every polygon. A
        # managed call per polygon overflows the host stack, so use the same
        # iterative continuation trampoline proven by the V8:2 baseline.
        "overlay": "main",
        "address": "80023C64",
        "target": (
            "RecompOne.Runtime.Sdk.V82Compat."
            "EnterDemolitionGeometry23C64"
        ),
        "mode": "pre",
    },
    {
        "overlay": "main",
        "address": "80023C64",
        "target": (
            "RecompOne.Runtime.Sdk.V82Compat."
            "LeaveDemolitionGeometryContinuation"
        ),
        "mode": "post",
    },
    {
        "overlay": "main",
        "address": "80055754",
        "target": "RecompOne.Runtime.Sdk.LibEtc.VSync",
        "mode": "replace",
    },
    {
        "overlay": "main",
        "address": "8001582C",
        "target": (
            "RecompOne.Runtime.Sdk.V82Compat."
            "ServiceDemolitionDrawSyncWait"
        ),
        "mode": "replace",
    },
    {
        # These are instruction-identical counterparts of V8:2's native
        # terrain packet writers (0x800288E0, 0x800290A8, 0x800297E8).
        # Bracketing them selects the terrain-specific GTE projection rules
        # required by the retail culling and packet clipping code.
        "overlay": "main",
        "address": "8002ABEC",
        "target": (
            "RecompOne.Runtime.Sdk.V82Compat."
            "BeginTerrainRoutePacketWrites"
        ),
        "mode": "pre",
    },
    {
        "overlay": "main",
        "address": "8002ABEC",
        "target": (
            "RecompOne.Runtime.Sdk.V82Compat."
            "EndTerrainRoutePacketWrites"
        ),
        "mode": "post",
    },
    {
        "overlay": "main",
        "address": "8002B3B4",
        "target": (
            "RecompOne.Runtime.Sdk.V82Compat."
            "BeginTerrainDetailPacketWrites"
        ),
        "mode": "pre",
    },
    {
        "overlay": "main",
        "address": "8002B3B4",
        "target": (
            "RecompOne.Runtime.Sdk.V82Compat."
            "EndTerrainDetailPacketWrites"
        ),
        "mode": "post",
    },
    {
        "overlay": "main",
        "address": "8002BAF4",
        "target": (
            "RecompOne.Runtime.Sdk.V82Compat."
            "BeginTerrainTransitionPacketWrites"
        ),
        "mode": "pre",
    },
    {
        "overlay": "main",
        "address": "8002BAF4",
        "target": (
            "RecompOne.Runtime.Sdk.V82Compat."
            "EndTerrainTransitionPacketWrites"
        ),
        "mode": "post",
    },
    {
        "overlay": "main",
        "address": "8002AE60",
        "target": (
            "RecompOne.Runtime.Sdk.V82Compat."
            "TagFirstCoarseTerrainPacket"
        ),
        "mode": "inline",
        "position": "after",
    },
    {
        "overlay": "main",
        "address": "8002AEC0",
        "target": (
            "RecompOne.Runtime.Sdk.V82Compat."
            "TagSecondCoarseTerrainPacket"
        ),
        "mode": "inline",
        "position": "after",
    },
    {
        "overlay": "main",
        "address": "8002B46C",
        "target": (
            "RecompOne.Runtime.Sdk.V82Compat."
            "TagFirstCoarseTerrainPacket"
        ),
        "mode": "inline",
        "position": "after",
    },
    {
        "overlay": "main",
        "address": "8002B4B4",
        "target": (
            "RecompOne.Runtime.Sdk.V82Compat."
            "TagSecondCoarseTerrainPacket"
        ),
        "mode": "inline",
        "position": "after",
    },
    {
        # Demolition's model renderer is the direct counterpart of V8:2's
        # 0x8002D9E0 renderer.  Keep the retail renderer and bracket it so the
        # GPU backend can associate emitted packets with the active model and
        # resolve its texture/material ownership.
        "overlay": "main",
        "address": "80030DEC",
        "target": (
            "RecompOne.Runtime.Sdk.V82Compat."
            "BeginDemolitionObjectRender"
        ),
        "mode": "inline",
        "position": "before",
    },
    {
        "overlay": "main",
        "address": "80030DEC",
        "target": (
            "RecompOne.Runtime.Sdk.V82Compat."
            "EndDemolitionObjectRender"
        ),
        "mode": "post",
    },
    {
        # The arena visibility tree is recursive in retail. Recompiled direct
        # recursion shares one CpuContext and becomes prohibitively slow on the
        # larger Demolition trees, so walk the same nodes on a host stack.
        "overlay": "main",
        "address": "800350B0",
        "target": (
            "RecompOne.Runtime.Sdk.V82Compat."
            "WalkDemolitionVisibilityTree"
        ),
        "mode": "replace",
    },
    {
        # Visibility leaves are intrusive object lists. Relocated arena data
        # can contain a repeated link; make the null-terminated retail walk
        # cycle-safe while retaining each object's native draw callback.
        "overlay": "main",
        "address": "80034DEC",
        "target": (
            "RecompOne.Runtime.Sdk.V82Compat."
            "DrawDemolitionVisibilityLeaf"
        ),
        "mode": "replace",
    },
    {
        # Pad each selected terrain row into the columns newly visible at
        # 16:9. The callee retains its native grid clamps.
        "overlay": "main",
        "address": "8001C954",
        "target": (
            "RecompOne.Runtime.Sdk.V82Compat."
            "ExpandTerrainRowSpan"
        ),
        "mode": "pre",
    },
    {
        # 0x8001CC78 is the terrain scan converter's entry wrapper, called once
        # per frame by the world renderer at 0x80035930. Its per-cell
        # visibility test reads the same gp-relative camera width the object
        # frustum uses, so without this the walker keeps testing terrain
        # against the authored 4:3 width while the viewport is 16:9 and
        # discards cells that are on screen. Padding the row spans cannot
        # recover those: the row is chosen before its span is widened.
        "overlay": "main",
        "address": "8001CC78",
        "target": (
            "RecompOne.Runtime.Sdk.V82Compat."
            "ExpandTerrainFrustum"
        ),
        "mode": "pre",
    },
    {
        "overlay": "main",
        "address": "8001CC78",
        "target": (
            "RecompOne.Runtime.Sdk.V82Compat."
            "RestoreTerrainFrustum"
        ),
        "mode": "post",
    },
    {
        # Demolition's double-buffer flip is the later shared-engine version
        # of V8:2 func_80014B3C. Retain its accounting, then move the next
        # frame into the reserved loose-port packet arena so the wider terrain
        # row spans cannot overwrite native packet state.
        "overlay": "main",
        "address": "800155C0",
        "target": (
            "RecompOne.Runtime.Sdk.V82Compat."
            "PrepareExpandedPrimitiveBuffer"
        ),
        "mode": "pre",
    },
    {
        "overlay": "main",
        "address": "800155C0",
        "target": (
            "RecompOne.Runtime.Sdk.V82Compat."
            "ActivateExpandedPrimitiveBuffer"
        ),
        "mode": "post",
    },
    {
        # Build object/scenery planes from the widened gameplay extent without
        # leaking the temporary value to later native code.
        "overlay": "main",
        "address": "800314F4",
        "target": (
            "RecompOne.Runtime.Sdk.V82Compat."
            "ExpandObjectFrustum"
        ),
        "mode": "pre",
    },
    {
        "overlay": "main",
        "address": "800314F4",
        "target": (
            "RecompOne.Runtime.Sdk.V82Compat."
            "RestoreObjectFrustum"
        ),
        "mode": "post",
    },
    {
        # Match the per-object bounding-radius test to those widened planes so
        # large scenery does not pop at the gameplay edges.
        "overlay": "main",
        "address": "80031730",
        "target": (
            "RecompOne.Runtime.Sdk.V82Compat."
            "WidenObjectVisibilityTest"
        ),
        "mode": "pre",
    },
    {
        # This is Demolition's per-frame world renderer. Marking this boundary
        # enables RecompOne's accelerated GPU backend only after the shell and
        # loading screens have completed their native VRAM transfers.
        "overlay": "main",
        "address": "80035930",
        "target": (
            "RecompOne.Runtime.Sdk.V82Compat."
            "BeginDemolitionGameplayFrame"
        ),
        "mode": "pre",
    },
    {
        "overlay": "main",
        "address": "80035930",
        "target": (
            "RecompOne.Runtime.Sdk.V82Compat."
            "SubmitDemolitionWorldOrderingTable"
        ),
        "mode": "post",
    },
    {
        "overlay": "main",
        "address": "8005C850",
        "target": "RecompOne.Runtime.Sdk.LibGpu.DrawSync",
        "mode": "replace",
    },
    {
        "overlay": "main",
        "address": "8005CE44",
        "target": "RecompOne.Runtime.Sdk.LibGpu.DrawOTag",
        "mode": "replace",
    },
    {
        "overlay": "main",
        "address": "8005CAFC",
        "target": "RecompOne.Runtime.Sdk.LibGpu.LoadImage",
        "mode": "replace",
    },
    {
        "overlay": "main",
        "address": "8005CB5C",
        "target": "RecompOne.Runtime.Sdk.LibGpu.StoreImage",
        "mode": "replace",
    },
    {
        "overlay": "main",
        "address": "8005C9D4",
        "target": "RecompOne.Runtime.Sdk.LibGpu.ClearImage",
        "mode": "replace",
    },
    {
        "overlay": "main",
        "address": "8005CA64",
        "target": "RecompOne.Runtime.Sdk.LibGpu.ClearImage",
        "mode": "replace",
    },
    {
        "overlay": "main",
        "address": "8005CBBC",
        "target": "RecompOne.Runtime.Sdk.LibGpu.MoveImage",
        "mode": "replace",
    },
    {
        "overlay": "main",
        "address": "8005CEB4",
        "target": "RecompOne.Runtime.Sdk.LibGpu.PutDrawEnv",
        "mode": "replace",
    },
    {
        "overlay": "main",
        "address": "8005D080",
        "target": "RecompOne.Runtime.Sdk.LibGpu.PutDispEnv",
        "mode": "replace",
    },
    {
        "overlay": "main",
        "address": "80018B60",
        "target": "RecompOne.Runtime.Sdk.LibCd.WaitForDemolitionSector",
        "mode": "replace",
    },
    {
        "overlay": "main",
        "address": "80018B98",
        "target": "RecompOne.Runtime.Sdk.LibCd.BeginDemolitionFileRead",
        "mode": "pre",
    },
    {
        "overlay": "main",
        "address": "80018EE0",
        "target": "RecompOne.Runtime.Sdk.LibCd.ReadDemolitionFileBytes",
        "mode": "replace",
    },
    {
        "overlay": "main",
        "address": "800190AC",
        "target": "RecompOne.Runtime.Sdk.LibCd.SeekDemolitionFile",
        "mode": "replace",
    },
    {
        "overlay": "main",
        "address": "80058CC4",
        "target": "RecompOne.Runtime.Sdk.LibCd.CdSyncCallback",
        "mode": "replace",
    },
    {
        "overlay": "main",
        "address": "80058CE4",
        "target": "RecompOne.Runtime.Sdk.LibCd.CdReadyCallback",
        "mode": "replace",
    },
    {
        "overlay": "main",
        "address": "80058D04",
        "target": "RecompOne.Runtime.Sdk.LibCd.CdControl",
        "mode": "replace",
    },
    {
        "overlay": "main",
        "address": "80058E40",
        "target": "RecompOne.Runtime.Sdk.LibCd.CdControlF",
        "mode": "replace",
    },
    {
        "overlay": "main",
        "address": "80058F74",
        "target": "RecompOne.Runtime.Sdk.LibCd.CdControlB",
        "mode": "replace",
    },
    {
        "overlay": "main",
        "address": "800590E4",
        "target": "RecompOne.Runtime.Sdk.LibCd.CdGetSector",
        "mode": "replace",
    },
    {
        "overlay": "main",
        "address": "80059934",
        "target": "RecompOne.Runtime.Sdk.LibCd.CdRead",
        "mode": "replace",
    },
    {
        "overlay": "main",
        "address": "80059AD0",
        "target": "RecompOne.Runtime.Sdk.LibCd.CdReadSync",
        "mode": "replace",
    },
    {
        "overlay": "main",
        "address": "800569A4",
        "target": "RecompOne.Runtime.Sdk.LibCdStream.StSetRing",
        "mode": "replace",
    },
    {
        "overlay": "main",
        "address": "800569D4",
        "target": "RecompOne.Runtime.Sdk.LibCdStream.StClearRing",
        "mode": "replace",
    },
    {
        "overlay": "main",
        "address": "80056A34",
        "target": "RecompOne.Runtime.Sdk.LibCdStream.StSetStream",
        "mode": "replace",
    },
    {
        "overlay": "main",
        "address": "80053498",
        "target": "RecompOne.Runtime.Sdk.V82Compat.DemolitionMalloc",
        "mode": "replace",
    },
    {
        "overlay": "main",
        "address": "80053510",
        "target": "RecompOne.Runtime.Sdk.V82Compat.DemolitionFree",
        "mode": "replace",
    },
    {
        "overlay": "main",
        "address": "800535C0",
        "target": "RecompOne.Runtime.Sdk.V82Compat.DemolitionRealloc",
        "mode": "replace",
    },
    {
        "overlay": "SHELL_SHELL",
        "address": "8010FBD0",
        "target": "RecompOne.Runtime.Sdk.LibCdStream.StFreeRing",
        "mode": "replace",
    },
    {
        "overlay": "SHELL_SHELL",
        "address": "8010FC80",
        "target": "RecompOne.Runtime.Sdk.LibCdStream.StGetNext",
        "mode": "replace",
    },
    {
        "overlay": "SHELL_SHELL",
        "address": "8010F32C",
        "target": "RecompOne.Runtime.Sdk.V82Compat.PreserveShellDecodeCallerPre",
        "mode": "pre",
    },
    {
        "overlay": "SHELL_SHELL",
        "address": "8010F32C",
        "target": "RecompOne.Runtime.Sdk.V82Compat.PreserveShellDecodeCallerPost",
        "mode": "post",
    },
    {
        "overlay": "SHELL_SHELL",
        "address": "8010EF04",
        "target": "RecompOne.Runtime.Sdk.V82Compat.PreserveShellImageDecodePre",
        "mode": "pre",
    },
    {
        "overlay": "SHELL_SHELL",
        "address": "8010EF04",
        "target": "RecompOne.Runtime.Sdk.V82Compat.PreserveShellImageDecodePost",
        "mode": "post",
    },
    {
        "overlay": "SHELL_SHELL",
        "address": "8010F644",
        "target": "RecompOne.Runtime.Sdk.V82Compat.RunDemolitionShellVlc",
        "mode": "replace",
    },
    {
        "overlay": "SHELL_SHELL",
        "address": "80110140",
        "target": "RecompOne.Runtime.Sdk.V8Compat.TranslateOverlayDmaSource",
        "mode": "pre",
    },
    {
        "overlay": "SHELL_SHELL",
        "address": "801122E8",
        "target": "RecompOne.Runtime.Sdk.V82Compat.WaitDemolitionCardOperation",
        "mode": "replace",
    },
    {
        "overlay": "SHELL_SHELL",
        "address": "80112FE8",
        "target": "RecompOne.Runtime.Sdk.V8Compat.WaitCardEvent",
        "mode": "replace",
    },
    {
        "overlay": "SHELL_SHELL",
        "address": "801130C0",
        "target": "RecompOne.Runtime.Sdk.V8Compat.WaitCardEvent",
        "mode": "replace",
    },
    {
        "overlay": "SHELL_LOAD",
        "address": "80108E74",
        "target": "RecompOne.Runtime.Sdk.V82Compat.RunDemolitionLoadVlc",
        "mode": "replace",
    },
    {
        "overlay": "main",
        "address": "80061404",
        "target": "RecompOne.Runtime.Sdk.LibPad.PadInitDirect",
        "mode": "replace",
    },
    {
        "overlay": "main",
        "address": "800612D4",
        "target": "RecompOne.Runtime.Sdk.LibPad.PadStartCom",
        "mode": "replace",
    },
    {
        "overlay": "main",
        "address": "800613A0",
        "target": "RecompOne.Runtime.Sdk.LibPad.PadStopCom",
        "mode": "replace",
    },
    {
        "overlay": "main",
        "address": "80060F34",
        "target": "RecompOne.Runtime.Sdk.LibPad.PadSetActAlign",
        "mode": "replace",
    },
    {
        "overlay": "main",
        "address": "80060EF4",
        "target": "RecompOne.Runtime.Sdk.LibPad.PadSetAct",
        "mode": "replace",
    },
    {
        "overlay": "main",
        "address": "800610A4",
        "target": "RecompOne.Runtime.Sdk.LibPad.PadSetMainMode",
        "mode": "replace",
    },
    {
        "overlay": "main",
        "address": "80061204",
        "target": "RecompOne.Runtime.Sdk.LibPad.PadGetState",
        "mode": "replace",
    },
]


def relative_posix(path: Path, start: Path) -> str:
    resolved = path.resolve()
    try:
        return Path(os.path.relpath(resolved, start.resolve())).as_posix()
    except ValueError:
        # Windows cannot express a relative path across drive letters.
        return resolved.as_posix()


def overlay_name(relative_path: Path) -> str:
    parts = [
        part.upper().replace("-", "_")
        for part in relative_path.with_suffix("").parts
    ]
    return "_".join(parts)


def discover_overlays(disc_root: Path) -> list[dict[str, object]]:
    overlay_roots = {"LEVELS", "SHARED", "SHELL"}
    preferred = [
        disc_root / "SHELL" / "SHELL.DLL",
        disc_root / "SHELL" / "LOAD.DLL",
    ]
    remaining = sorted(
        (
            path
            for path in disc_root.rglob("*.DLL")
            if path not in preferred
            and path.relative_to(disc_root).parts[0].upper() in overlay_roots
        ),
        key=lambda path: path.relative_to(disc_root).as_posix().upper(),
    )

    overlays: list[dict[str, object]] = []
    seen_names: set[str] = set()
    for path in [*preferred, *remaining]:
        if not path.is_file():
            raise FileNotFoundError(f"required overlay is missing: {path}")
        relative = path.relative_to(disc_root)
        name = overlay_name(relative)
        if name in seen_names:
            raise ValueError(f"duplicate generated overlay name: {name}")
        seen_names.add(name)
        overlays.append(
            overlay := {
                "name": name,
                "base": "0x80100000",
                "file": str(relative).replace("/", "\\"),
                "v8Relocate": True,
                "linearSweep": True,
            }
        )
        if name in EXTRA_OVERLAY_FUNCTIONS:
            overlay["functions"] = [
                {"address": address}
                for address in EXTRA_OVERLAY_FUNCTIONS[name]
            ]
    return overlays


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cue", type=Path)
    parser.add_argument("--disc-root", type=Path, default=DEFAULT_DISC_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    cue = args.cue.resolve() if args.cue else None
    disc_root = args.disc_root.resolve()
    output = args.output.resolve()
    if cue is not None and not cue.is_file():
        raise FileNotFoundError(f"retail CUE is missing: {cue}")
    if not (disc_root / "SYSTEM.CNF").is_file():
        raise FileNotFoundError(
            f"extracted disc root is missing SYSTEM.CNF: {disc_root}"
        )
    if not (disc_root / MAIN_EXE).is_file():
        raise FileNotFoundError(
            f"extracted main executable is missing: {disc_root / MAIN_EXE}"
        )

    output.mkdir(parents=True, exist_ok=True)
    overlays = discover_overlays(disc_root)
    config = {
        "game": {
            "id": "SLUS-01183",
            "name": "StarWarsDemolitionPC",
            "title": "Star Wars: Demolition PC",
            "output": "generated",
        },
        "loose": relative_posix(disc_root, output),
        "debug": False,
        "linearSweep": True,
        "functions": [
            {"address": address} for address in EXTRA_MAIN_FUNCTIONS
        ],
        "overlays": overlays,
        "stubs": [],
        "ignored": [],
        "patches": PROVEN_PATCHES,
    }

    config_path = output / "demolition.recompone.json"
    config_path.write_text(
        json.dumps(config, indent=2) + "\n", encoding="utf-8"
    )

    host_source = Path(__file__).resolve().parent / "reference-host"
    generated_project = output / "generated"
    generated_project.mkdir(parents=True, exist_ok=True)
    for host_file in ("Program.cs", "StarWarsDemolitionPC.csproj"):
        shutil.copy2(host_source / host_file, generated_project / host_file)

    print(f"Wrote {config_path}")
    print(f"Configured {len(overlays)} relocatable overlays")
    print(f"Refreshed host project in {generated_project}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
