@echo off
set EXE_PATH=bin\Release\net472\HachimiDX.exe

if exist "%EXE_PATH%" (
    del "%EXE_PATH%"
)

@echo on
dotnet build -c Release

@echo off
if exist "%EXE_PATH%" (
    copy "%EXE_PATH%" "."
    exit
) else (
    pause
)
