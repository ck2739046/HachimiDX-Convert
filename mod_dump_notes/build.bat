if exist "bin\Release\net472\Dump_Notes.dll" (
    del "bin\Release\net472\Dump_Notes.dll"
)

dotnet build -c Release

REM 复制dll到根目录
if exist "bin\Release\net472\Dump_Notes.dll" (
    copy "bin\Release\net472\Dump_Notes.dll" "."
) else (
    pause
)

REM 复制dll到游戏
if exist "Dump_Notes.dll" (
    copy "Dump_Notes.dll" "C:\maimai\160\Package\Mods"
    exit
) else (
    echo.
    powershell write-host "Error: Dump_Notes.dll not found" -ForegroundColor Red
    pause
)
