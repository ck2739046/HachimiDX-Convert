using System;
using System.Diagnostics;

class Program
{
    static void Main()
    {
        var psi = new ProcessStartInfo
        {
            FileName = @".\python\python.exe",
            Arguments = "-u main.py",
            UseShellExecute = false
        };

        var proc = Process.Start(psi);
        proc?.WaitForExit();

        Console.WriteLine();
        Console.WriteLine("Press any key to continue...\n按任意键继续...");
        Console.ReadKey(true);
    }
}
