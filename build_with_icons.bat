@echo off
echo Building Auto Organizer with custom icons...

REM Check if Python is installed
where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo Python not found! Please install Python 3.
    pause
    exit /b 1
)

REM Ensure PyInstaller is installed
python -m pip install --upgrade PyInstaller PyQt5 pywin32 winshell

REM Clean previous build folders if they exist
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

REM List all icon files
echo Icons that will be included:
echo - icon.ico
echo - watch.png
echo - settings.png
echo - logs.png
echo - info.png
echo - update.png

REM Build directly using PyInstaller
python -m PyInstaller --clean ^
    --name="Auto Organizer" ^
    --icon=icon.ico ^
    --windowed ^
    --add-data="icon.ico;." ^
    --add-data="watch.png;." ^
    --add-data="settings.png;." ^
    --add-data="logs.png;." ^
    --add-data="info.png;." ^
    --add-data="update.png;." ^
    --add-data="version.txt;." ^
    watcher_app.py

REM Check if build succeeded
if not exist "dist\Auto Organizer.exe" (
    echo Build failed! Executable not found.
    pause
    exit /b 1
)

REM Verify the icons are in the dist folder
echo Verifying icons in dist folder:
dir "dist\Auto Organizer\*png" 2>nul || echo No PNG files found in dist folder!
dir "dist\Auto Organizer\icon.ico" 2>nul || echo icon.ico not found in dist folder!

echo Build complete!
echo Executable location: dist\Auto Organizer\Auto Organizer.exe
pause 