using RecompOne.Runtime.Context;
using RecompOne.Runtime.Memory;

namespace RecompOne.Runtime.Sdk;

public static class LibEtc
{
    static int _vcount;
    static bool _demolitionShellRepeatVSync;
    static readonly bool TraceVSync =
        Environment.GetEnvironmentVariable("RECOMPONE_TRACE_VSYNC") == "1";

    public static void VSync(CpuContext c, IMemory m)
    {
        int mode = (int)c.A0;
        Log.Sdk($"VSync({mode})");
        if (TraceVSync && (_vcount < 10 || (_vcount % 300) == 0))
            Console.Error.WriteLine(
                $"[VSync] enter count={_vcount} mode={mode} caller=0x{c.RA:X8}");
        if (mode < 0) { c.V0 = (uint)_vcount; return; }
        if (mode == 1) { c.V0 = 0; return; }

        bool renderVideo = true;
        // Demolition's 3D SHELL is a 30 Hz loop which waits for two VBlanks
        // at 0x8010DC70. The first VBlank presents the completed page; its
        // interrupt then prepares the next page, so asking the host renderer
        // to sample again before the translated loop has submitted that page
        // exposes the cleared target as a black 60 Hz flash. Keep servicing
        // input, audio, CD and the interrupt on both VBlanks, but retain the
        // first image for the second display interval just as the PS1 does.
        if (mode == 0 &&
            c.RA == 0x8010DC70u &&
            Runtime.GameTitle.Contains(
                "Demolition", StringComparison.OrdinalIgnoreCase))
        {
            renderVideo = !_demolitionShellRepeatVSync;
            _demolitionShellRepeatVSync = !_demolitionShellRepeatVSync;
        }
        Runtime.PresentFrame(renderVideo);
        _vcount++;
        if (TraceVSync && _vcount <= 10)
            Console.Error.WriteLine($"[VSync] leave count={_vcount}");
        V8Compat.TraceGameplayHeartbeat(c, m);
        c.V0 = 0;
    }
}
