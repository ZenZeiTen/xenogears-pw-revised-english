// Xenogears Perfect Works 0.11.4 - Revised English Script Patcher
// Applies the embedded BPS patches to an unmodified Perfect Works 0.11.4 disc image.
// The input is never modified; a new .bin and .cue are written next to it.
// Licensed GPL-3.0-or-later, like the Perfect Works script it revises.
using System.Reflection;
using System.Text;

static class Program
{
    record Patch(string Name, byte[] Data, uint SourceCrc, uint TargetCrc, long SourceSize, long TargetSize, string Disc);

    static int Main(string[] args)
    {
        Console.OutputEncoding = Encoding.UTF8;
        Console.WriteLine("Xenogears Perfect Works 0.11.4 - Revised English Script Patcher 1.0.0");
        Console.WriteLine("Translation changes only (no gameplay or reward changes).\n");
        var patches = LoadPatches();
        var inputs = args.Length > 0 ? args.ToList() : Ask();
        int failures = 0;
        foreach (var raw in inputs)
        {
            try { PatchOne(raw, patches); }
            catch (Exception e) { failures++; Console.WriteLine($"  ERROR: {e.Message}\n"); }
        }
        if (args.Length == 0 || failures > 0) { Console.WriteLine("Press Enter to exit."); Console.ReadLine(); }
        return failures == 0 ? 0 : 1;
    }

    static List<string> Ask()
    {
        Console.WriteLine("Drag a Perfect Works 0.11.4 disc image (.bin or .cue) onto this window and press Enter.");
        Console.WriteLine("You can patch disc 1 and disc 2 one after the other; an empty line starts patching.\n");
        var list = new List<string>();
        while (true)
        {
            Console.Write("> ");
            var line = Console.ReadLine();
            if (string.IsNullOrWhiteSpace(line)) break;
            list.Add(line.Trim().Trim('"'));
        }
        return list;
    }

    static List<Patch> LoadPatches()
    {
        var asm = Assembly.GetExecutingAssembly();
        var result = new List<Patch>();
        foreach (var name in asm.GetManifestResourceNames().Where(n => n.EndsWith(".bps")))
        {
            using var s = asm.GetManifestResourceStream(name)!;
            using var ms = new MemoryStream();
            s.CopyTo(ms);
            var d = ms.ToArray();
            if (Crc32.Compute(d, 0, d.Length - 4) != BitConverter.ToUInt32(d, d.Length - 4))
                throw new InvalidDataException($"embedded patch {name} is corrupt");
            int pos = 4;
            long ssz = ReadNum(d, ref pos), tsz = ReadNum(d, ref pos);
            result.Add(new Patch(name, d, BitConverter.ToUInt32(d, d.Length - 12), BitConverter.ToUInt32(d, d.Length - 8),
                                 ssz, tsz, name.Contains("CD1") ? "disc 1" : "disc 2"));
        }
        return result;
    }

    static void PatchOne(string input, List<Patch> patches)
    {
        var path = input;
        if (path.EndsWith(".cue", StringComparison.OrdinalIgnoreCase))
        {
            var line = File.ReadLines(path).FirstOrDefault(l => l.TrimStart().StartsWith("FILE", StringComparison.OrdinalIgnoreCase))
                       ?? throw new InvalidDataException("the .cue file names no .bin file");
            int a = line.IndexOf('"'), b = line.LastIndexOf('"');
            path = Path.Combine(Path.GetDirectoryName(Path.GetFullPath(path))!, line.Substring(a + 1, b - a - 1));
        }
        if (!File.Exists(path)) throw new FileNotFoundException($"not found: {path}");
        var len = new FileInfo(path).Length;
        Console.WriteLine($"Checking {Path.GetFileName(path)} ({len / 1048576} MB)...");
        var candidates = patches.Where(p => p.SourceSize == len).ToList();
        if (candidates.Count == 0) throw new InvalidDataException("this image is not an unmodified Perfect Works 0.11.4 disc (size does not match)");
        uint crc = Crc32.OfFile(path);
        var patch = candidates.FirstOrDefault(p => p.SourceCrc == crc)
                    ?? throw new InvalidDataException($"CRC32 {crc:x8} does not match Perfect Works 0.11.4 (already patched, or a different build?)");
        var dir = Path.GetDirectoryName(Path.GetFullPath(path))!;
        var outBin = Path.Combine(dir, Path.GetFileNameWithoutExtension(path) + "_EN_revised.bin");
        if (File.Exists(outBin)) throw new IOException($"{Path.GetFileName(outBin)} already exists; move or delete it first");
        Console.WriteLine($"  Recognized Perfect Works 0.11.4 {patch.Disc}. Writing {Path.GetFileName(outBin)}...");
        var tmp = outBin + ".part";
        try
        {
            uint outCrc = Apply(path, patch.Data, tmp);
            if (outCrc != patch.TargetCrc) throw new InvalidDataException("output CRC mismatch; nothing was written");
            File.Move(tmp, outBin);
        }
        finally { if (File.Exists(tmp)) File.Delete(tmp); }
        var outCue = Path.ChangeExtension(outBin, ".cue");
        File.WriteAllText(outCue, $"FILE \"{Path.GetFileName(outBin)}\" BINARY\r\n  TRACK 01 MODE2/2352\r\n    INDEX 01 00:00:00\r\n");
        Console.WriteLine($"  Done. Load {Path.GetFileName(outCue)} in your emulator.\n");
    }

    static long ReadNum(byte[] d, ref int pos)
    {
        long n = 0, shift = 1;
        while (true)
        {
            byte x = d[pos++];
            n += (x & 0x7F) * shift;
            if ((x & 0x80) != 0) return n;
            shift <<= 7;
            n += shift;
        }
    }

    // BPS decoder: SourceRead / TargetRead / SourceCopy / TargetCopy, streamed to disk.
    static uint Apply(string srcPath, byte[] p, string outPath)
    {
        using var src = new FileStream(srcPath, FileMode.Open, FileAccess.Read, FileShare.Read, 1 << 20);
        using var dst = new FileStream(outPath, FileMode.CreateNew, FileAccess.ReadWrite, FileShare.None, 1 << 20);
        int pos = 4;
        ReadNum(p, ref pos); long tsz = ReadNum(p, ref pos); long msz = ReadNum(p, ref pos);
        pos += (int)msz;
        long o = 0, srcRel = 0, tgtRel = 0;
        int end = p.Length - 12;
        var buf = new byte[1 << 20];
        var crc = new Crc32();
        int lastPct = -1;
        void Copy(Stream from, long at, long n)
        {
            while (n > 0)
            {
                int k = (int)Math.Min(n, buf.Length);
                from.Position = at;
                from.ReadExactly(buf, 0, k);
                dst.Position = o;
                dst.Write(buf, 0, k);
                crc.Update(buf, 0, k);
                at += k; o += k; n -= k;
            }
        }
        while (pos < end)
        {
            long d = ReadNum(p, ref pos);
            long n = (d >> 2) + 1;
            switch (d & 3)
            {
                case 0: Copy(src, o, n); break;
                case 1:
                    dst.Position = o; dst.Write(p, pos, (int)n); crc.Update(p, pos, (int)n);
                    pos += (int)n; o += n; break;
                case 2:
                {
                    long r = ReadNum(p, ref pos);
                    srcRel += (r & 1) != 0 ? -(r >> 1) : (r >> 1);
                    Copy(src, srcRel, n); srcRel += n; break;
                }
                default:
                {
                    long r = ReadNum(p, ref pos);
                    tgtRel += (r & 1) != 0 ? -(r >> 1) : (r >> 1);
                    for (long i = 0; i < n; i++)       // byte by byte: source and destination may overlap
                    {
                        dst.Position = tgtRel++; int b = dst.ReadByte();
                        dst.Position = o++; dst.WriteByte((byte)b); crc.Update(new[] { (byte)b }, 0, 1);
                    }
                    break;
                }
            }
            int pct = (int)(100 * o / tsz);
            if (pct / 10 != lastPct / 10) { Console.Write($"\r  {pct,3}%"); lastPct = pct; }
        }
        Console.WriteLine("\r  100%");
        if (o != tsz) throw new InvalidDataException("output size mismatch");
        return crc.Value;
    }
}

sealed class Crc32
{
    static readonly uint[] Table = Enumerable.Range(0, 256).Select(i =>
    {
        uint c = (uint)i;
        for (int k = 0; k < 8; k++) c = (c & 1) != 0 ? 0xEDB88320u ^ (c >> 1) : c >> 1;
        return c;
    }).ToArray();
    uint state = 0xFFFFFFFFu;
    public uint Value => ~state;
    public void Update(byte[] d, int off, int len)
    {
        uint c = state;
        for (int i = off; i < off + len; i++) c = Table[(c ^ d[i]) & 0xFF] ^ (c >> 8);
        state = c;
    }
    public static uint Compute(byte[] d, int off, int len) { var c = new Crc32(); c.Update(d, off, len); return c.Value; }
    public static uint OfFile(string path)
    {
        var c = new Crc32();
        using var f = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.Read, 1 << 20);
        var buf = new byte[1 << 20];
        int n;
        while ((n = f.Read(buf, 0, buf.Length)) > 0) c.Update(buf, 0, n);
        return c.Value;
    }
}
