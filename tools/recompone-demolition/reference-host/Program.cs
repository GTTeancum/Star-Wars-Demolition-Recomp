using RecompOne.Runtime.Config;
using RecompOne.Runtime.Memory;
using Recompiled;

string launchDirectory = Environment.CurrentDirectory;
string executableDirectory =
    Path.GetDirectoryName(Environment.ProcessPath) ?? AppContext.BaseDirectory;
Environment.CurrentDirectory = executableDirectory;

if (args.Length > 1)
{
    PrintUsage();
    return 1;
}

string source = args.Length == 1
    ? Path.GetFullPath(args[0], launchDirectory)
    : FindSource(executableDirectory);

if (!Directory.Exists(source) ||
    !File.Exists(Path.Combine(source, "SYSTEM.CNF")))
{
    throw new FileNotFoundException(
        $"Expected a Star Wars: Demolition loose-file directory: {source}");
}

ConfigManager.Load();
RecompOne.Runtime.Runtime.SetLoosePath(source);
ConfigManager.Game.CdPath = "";
Console.WriteLine($"[Host] standalone-loose={source}");
ConfigManager.SaveGame();

PreloadBundledNative("SDL2.dll");
RecompOne.Runtime.Runtime.SetMode(RecompOne.Runtime.RunMode.Devkit);
Entry.Run(new PSMemory(), null, source);
return 0;

static string FindSource(string directory)
{
    if (File.Exists(Path.Combine(directory, "SYSTEM.CNF")))
        return directory;
    throw new FileNotFoundException(
        "No loose game files found. Pass their directory, or publish the executable into that directory.");
}

static void PrintUsage() => Console.Error.WriteLine(
    "usage: StarWarsDemolitionPC [loose-game-directory]");

static void PreloadBundledNative(string fileName)
{
    string? searchDirectories =
        AppContext.GetData("NATIVE_DLL_SEARCH_DIRECTORIES") as string;
    if (string.IsNullOrWhiteSpace(searchDirectories))
        return;

    foreach (string directory in searchDirectories.Split(
                 Path.PathSeparator, StringSplitOptions.RemoveEmptyEntries))
    {
        string candidate = Path.Combine(directory, fileName);
        if (!File.Exists(candidate))
            continue;
        System.Runtime.InteropServices.NativeLibrary.Load(candidate);
        Console.WriteLine($"[Host] preloaded bundled native library: {fileName}");
        return;
    }
}
