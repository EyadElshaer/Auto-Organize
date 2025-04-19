@echo off
echo Building Auto Organizer...

REM Try to close any running instances of Auto Organizer
echo Closing any running instances of Auto Organizer...
taskkill /F /IM "Auto Organizer.exe" /T > nul 2>&1

REM Add a small delay to ensure processes are fully terminated
timeout /t 2 /nobreak > nul

REM Check if Python is installed
where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo Python not found! Please install Python 3.
    pause
    exit /b 1
)

REM Ensure PyInstaller is installed
python -m pip install PyInstaller PyQt5 pywin32 winshell

REM Create PNG icons only if they don't exist
echo Checking for necessary icon files...
if not exist watch.png (
    echo Creating watch.png...
    copy icon.ico watch.png >nul 2>nul
)
if not exist settings.png (
    echo Creating settings.png...
    copy icon.ico settings.png >nul 2>nul
)
if not exist logs.png (
    echo Creating logs.png...
    copy icon.ico logs.png >nul 2>nul
)
if not exist info.png (
    echo Creating info.png...
    copy icon.ico info.png >nul 2>nul
)
if not exist update.png (
    echo Creating update.png...
    copy icon.ico update.png >nul 2>nul
)

REM Build the application
echo Building with PyInstaller...
python build_exe.py

echo Build complete!
echo Executable location: dist/Auto Organizer.exe
pause