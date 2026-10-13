// MIT - RyanSantr. Prepara o runtime local uma vez, sem instalar servicos.
using System;
using System.ComponentModel;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using System.Windows.Forms;

[assembly: AssemblyTitle("2DCam Studio")]
[assembly: AssemblyProduct("2DCam Studio")]
[assembly: AssemblyCompany("RyanSantr")]
[assembly: AssemblyVersion("@@VERSION@@")]
[assembly: AssemblyFileVersion("@@VERSION@@")]

static class Launcher
{
    internal const string Version = "@@VERSION@@";
    internal const string PayloadHash = "@@PAYLOAD_HASH@@";
    internal static string RuntimeRoot;
    internal static string Runtime;
    internal static string[] Arguments;
    internal static int ExitCode;

    [STAThread]
    static int Main(string[] arguments)
    {
        Arguments = arguments;
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        try
        {
            string custom = Environment.GetEnvironmentVariable("AVATARCAM_RUNTIME_DIR");
            RuntimeRoot = Path.GetFullPath(String.IsNullOrEmpty(custom) ?
                Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "2DCam", "runtime") : custom);
            Runtime = Path.Combine(RuntimeRoot, Version + "-" + PayloadHash.Substring(0, 12));
            Application.Run(new LoadingWindow());
        }
        catch (Exception error) { ShowFailure(error); ExitCode = 1; }
        return ExitCode;
    }

    internal static void ShowFailure(Exception error)
    {
        MessageBox.Show("Não foi possível abrir o 2DCam.\n\n" + error.Message +
            "\n\nSe o app já estiver aberto, feche-o e tente novamente. Seus personagens e ajustes ficam preservados.",
            "2DCam Studio", MessageBoxButtons.OK, MessageBoxIcon.Error);
    }

    static bool Ready()
    {
        string marker = Path.Combine(Runtime, ".ready");
        if (!File.Exists(marker) || File.ReadAllText(marker) != PayloadHash) return false;
        using (Stream stream = Assembly.GetExecutingAssembly().GetManifestResourceStream("2DCam.files"))
        using (StreamReader reader = new StreamReader(stream, Encoding.UTF8))
        {
            string line;
            while ((line = reader.ReadLine()) != null)
                if (!File.Exists(SafePath(Runtime, line))) return false;
        }
        return true;
    }

    static string SafePath(string root, string name)
    {
        if (Path.IsPathRooted(name) || name.Contains(":")) throw new InvalidDataException("Caminho inválido no aplicativo.");
        string prefix = Path.GetFullPath(root).TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
        string target = Path.GetFullPath(Path.Combine(prefix, name.Replace('/', Path.DirectorySeparatorChar)));
        if (!target.StartsWith(prefix, StringComparison.OrdinalIgnoreCase)) throw new InvalidDataException("Caminho inválido no aplicativo.");
        return target;
    }

    static void DeleteOwnStage(string stage)
    {
        string expected = Runtime + ".preparing-" + Process.GetCurrentProcess().Id;
        if (Path.GetFullPath(stage) != Path.GetFullPath(expected)) throw new InvalidOperationException("Pasta temporária inválida.");
        SafePath(RuntimeRoot, Path.GetFileName(stage));
        if (Directory.Exists(stage)) Directory.Delete(stage, true);
    }

    internal static void Prepare(BackgroundWorker worker)
    {
        Directory.CreateDirectory(RuntimeRoot);
        using (Mutex mutex = new Mutex(false, "Local\\2DCam-Prepare-" + PayloadHash.Substring(0, 24)))
        {
            bool acquired = false;
            try
            {
                try { acquired = mutex.WaitOne(180000); }
                catch (AbandonedMutexException) { acquired = true; }
                if (!acquired) throw new IOException("O app ainda está preparando os componentes. Aguarde e tente novamente.");
                if (Ready()) return;
                string stage = Runtime + ".preparing-" + Process.GetCurrentProcess().Id;
                SafePath(RuntimeRoot, Path.GetFileName(stage));
                if (Directory.Exists(stage)) throw new IOException("Uma preparação anterior não terminou. Tente abrir novamente.");
                try
                {
                    using (Stream stream = Assembly.GetExecutingAssembly().GetManifestResourceStream("2DCam.payload"))
                    {
                        using (SHA256 hash = SHA256.Create())
                        {
                            string actual = BitConverter.ToString(hash.ComputeHash(stream)).Replace("-", "").ToLowerInvariant();
                            if (actual != PayloadHash) throw new InvalidDataException("O download está incompleto ou corrompido. Baixe o EXE novamente.");
                        }
                        stream.Position = 0;
                        using (ZipArchive archive = new ZipArchive(stream, ZipArchiveMode.Read, true))
                        {
                            long total = 0; foreach (ZipArchiveEntry entry in archive.Entries) total += entry.Length;
                            DriveInfo drive = new DriveInfo(Path.GetPathRoot(RuntimeRoot));
                            if (drive.AvailableFreeSpace < total + 64 * 1024 * 1024)
                                throw new IOException("Libere espaço no disco para preparar o aplicativo (aproximadamente " + ((total + 1048575) / 1048576) + " MB).");
                            Directory.CreateDirectory(stage); long written = 0; int reported = -1;
                            foreach (ZipArchiveEntry entry in archive.Entries)
                            {
                                if (worker.CancellationPending) throw new OperationCanceledException();
                                string target = SafePath(stage, entry.FullName);
                                Directory.CreateDirectory(Path.GetDirectoryName(target));
                                using (Stream source = entry.Open()) using (FileStream output = File.Create(target)) source.CopyTo(output, 65536);
                                if (new FileInfo(target).Length != entry.Length) throw new InvalidDataException("Arquivo incompleto no aplicativo.");
                                written += entry.Length;
                                int percent = total == 0 ? 100 : (int)(written * 100 / total);
                                if (percent != reported) { worker.ReportProgress(percent); reported = percent; }
                            }
                        }
                    }
                    File.WriteAllText(Path.Combine(stage, ".ready"), PayloadHash);
                    // Uma copia incompleta anterior e preservada; dados do usuario ficam em outra pasta.
                    if (Directory.Exists(Runtime))
                    {
                        string previous = Runtime + ".incomplete-" + Guid.NewGuid().ToString("N");
                        SafePath(RuntimeRoot, Path.GetFileName(previous));
                        Directory.Move(Runtime, previous);
                    }
                    Directory.Move(stage, Runtime);
                }
                finally { DeleteOwnStage(stage); }
            }
            finally { if (acquired) mutex.ReleaseMutex(); }
        }
    }

    internal static string Quote(string value)
    {
        StringBuilder text = new StringBuilder("\""); int slashes = 0;
        foreach (char ch in value)
        {
            if (ch == '\\') { slashes++; continue; }
            if (ch == '"') { text.Append('\\', slashes * 2 + 1); text.Append(ch); }
            else { text.Append('\\', slashes); text.Append(ch); }
            slashes = 0;
        }
        text.Append('\\', slashes * 2); text.Append('"'); return text.ToString();
    }

    internal static Process StartApp()
    {
        StringBuilder arguments = new StringBuilder();
        foreach (string value in Arguments) { if (arguments.Length > 0) arguments.Append(' '); arguments.Append(Quote(value)); }
        ProcessStartInfo start = new ProcessStartInfo(Path.Combine(Runtime, "2DCamStudio.exe"), arguments.ToString());
        start.WorkingDirectory = Runtime; start.UseShellExecute = false;
        start.EnvironmentVariables["AVATARCAM_CACHED_RUNTIME"] = "1";
        start.EnvironmentVariables["AVATARCAM_LAUNCHER"] = Assembly.GetExecutingAssembly().Location;
        return Process.Start(start);
    }
}

sealed class LoadingWindow : Form
{
    readonly BackgroundWorker worker = new BackgroundWorker();
    readonly ProgressBar progress = new ProgressBar();
    readonly Label status = new Label();
    bool finished;
    internal LoadingWindow()
    {
        Text = "2DCam Studio"; ClientSize = new Size(430, 145); FormBorderStyle = FormBorderStyle.FixedDialog;
        MaximizeBox = false; StartPosition = FormStartPosition.CenterScreen; BackColor = Color.FromArgb(21, 27, 35);
        ForeColor = Color.FromArgb(231, 237, 244); Font = new Font("Segoe UI", 10);
        Label title = new Label(); title.Text = "2DCam Studio"; title.Font = new Font("Segoe UI", 18); title.SetBounds(22, 18, 370, 36);
        status.Text = "Preparando o aplicativo…"; status.SetBounds(24, 66, 380, 24);
        progress.SetBounds(24, 103, 382, 15); Controls.Add(title); Controls.Add(status); Controls.Add(progress);
        try { Icon = Icon.ExtractAssociatedIcon(Assembly.GetExecutingAssembly().Location); } catch { }
        worker.WorkerReportsProgress = true; worker.WorkerSupportsCancellation = true;
        worker.DoWork += delegate { Launcher.Prepare(worker); };
        worker.ProgressChanged += delegate(object sender, ProgressChangedEventArgs args) { progress.Value = args.ProgressPercentage; };
        worker.RunWorkerCompleted += delegate(object sender, RunWorkerCompletedEventArgs args)
        {
            finished = true;
            if (args.Error is OperationCanceledException) { Launcher.ExitCode = 2; Close(); return; }
            if (args.Error != null) { Hide(); Launcher.ShowFailure(args.Error); Launcher.ExitCode = 1; Close(); return; }
            try
            {
                status.Text = "Abrindo o personagem…";
                using (Process child = Launcher.StartApp()) { }
            }
            catch (Exception error) { Hide(); Launcher.ShowFailure(error); Launcher.ExitCode = 1; }
            Close();
        };
        Shown += delegate { worker.RunWorkerAsync(); };
        FormClosing += delegate(object sender, FormClosingEventArgs args)
        { if (!finished) { worker.CancelAsync(); status.Text = "Cancelando…"; args.Cancel = true; } };
    }
}
