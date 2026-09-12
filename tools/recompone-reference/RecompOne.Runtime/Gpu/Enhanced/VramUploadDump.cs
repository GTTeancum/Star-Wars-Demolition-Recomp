namespace RecompOne.Runtime.Enhanced;

/// <summary>
/// Records every image the game uploads into VRAM, keyed by the content of the
/// upload rather than by where it lands. A texture pack is built offline from
/// these: the PlayStation upload is the unit a Dreamcast texture replaces, and
/// hashing its words gives a stable name for the pair regardless of which
/// VRAM page the allocator happened to choose on a given run.
/// </summary>
internal static class VramUploadDump
{
    static readonly string? Directory =
        Environment.GetEnvironmentVariable("RECOMPONE_VRAM_UPLOAD_DUMP_DIR");

    static readonly object Gate = new();
    static readonly HashSet<ulong> Written = [];
    static ushort[] _words = new ushort[64 * 1024];
    static int _x, _y, _width, _height, _count;
    static bool _active;
    static StreamWriter? _index;

    internal static bool Enabled => Directory != null;

    internal static void Begin(int x, int y, int width, int height)
    {
        if (Directory == null)
            return;
        lock (Gate)
        {
            _x = x;
            _y = y;
            _width = width;
            _height = height;
            _count = 0;
            _active = width > 0 && height > 0;
            int needed = width * height;
            if (_active && _words.Length < needed)
                _words = new ushort[needed];
        }
    }

    internal static void Put(ushort word)
    {
        if (Directory == null)
            return;
        lock (Gate)
        {
            if (!_active || _count >= _words.Length)
                return;
            _words[_count++] = word;
        }
    }

    internal static void Complete()
    {
        if (Directory == null)
            return;
        lock (Gate)
        {
            if (!_active)
                return;
            _active = false;
            int expected = _width * _height;
            if (_count != expected)
                return;
            ulong hash = 14695981039346656037UL;
            void Add(byte value)
            {
                hash ^= value;
                hash *= 1099511628211UL;
            }
            Add((byte)_width);
            Add((byte)(_width >> 8));
            Add((byte)_height);
            Add((byte)(_height >> 8));
            for (int index = 0; index < expected; index++)
            {
                Add((byte)_words[index]);
                Add((byte)(_words[index] >> 8));
            }
            System.IO.Directory.CreateDirectory(Directory);
            _index ??= new StreamWriter(
                Path.Combine(Directory, "uploads.txt"), append: false)
            { AutoFlush = true };
            // Every upload is listed, including repeats, because the same
            // content is re-uploaded to different pages between arenas and the
            // placement is what a VRAM-level replacement has to follow.
            _index.WriteLine(
                $"{hash:x16} {_x} {_y} {_width} {_height}");
            if (!Written.Add(hash))
                return;
            var bytes = new byte[expected * 2];
            for (int index = 0; index < expected; index++)
            {
                bytes[index * 2] = (byte)_words[index];
                bytes[index * 2 + 1] = (byte)(_words[index] >> 8);
            }
            File.WriteAllBytes(
                Path.Combine(
                    Directory, $"{hash:x16}_{_width}x{_height}.bin"),
                bytes);
        }
    }
}
