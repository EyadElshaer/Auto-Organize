@echo off
echo Building minimal installer...

REM Check if Inno Setup is installed
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" (
    set "ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
) else if exist "C:\Program Files\Inno Setup 6\ISCC.exe" (
    set "ISCC=C:\Program Files\Inno Setup 6\ISCC.exe"
) else (
    echo Inno Setup not found.
    echo Please install Inno Setup 6 from: https://jrsoftware.org/isdl.php
    goto :end
)

REM Create dummy file if needed
if not exist "dist" mkdir dist
if not exist "dist\dummy.exe" (
    echo Creating dummy executable...
    copy /Y "%WINDIR%\notepad.exe" "dist\dummy.exe" > nul
    echo Created dummy executable
)

REM Build installer
echo Building installer...
"%ISCC%" simple_installer.iss

if %ERRORLEVEL% neq 0 (
    echo Failed to build installer.
) else (
    echo Installer built successfully: %CD%\AutoOrganizerSetup.exe
)

:end
pause 