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
