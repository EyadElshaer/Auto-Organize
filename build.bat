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

REM Ensure required packages are installed
python -m pip install PyInstaller PyQt5 pywin32 winshell

REM Clean up previous build artifacts
echo Cleaning up previous builds...
if exist "build" rd /s /q "build"
if exist "dist" rd /s /q "dist"

REM Ensure icons directory exists and all required icons are present
echo Checking icons...
if not exist "icons" mkdir icons
if not exist "icons\icon.ico" (
    echo Error: icons\icon.ico not found!
    pause
    exit /b 1
)

REM Create the spec file with proper icon paths
echo Creating PyInstaller spec file...
python -c "import PyInstaller.__main__; PyInstaller.__main__.run(['--name=Auto Organizer', '--onefile', '--windowed', '--icon=icons/icon.ico', '--add-data=icons;icons', '--add-data=version.txt;.', 'watcher_app.py'])"

REM Run PowerShell script with admin rights
powershell -Command "Start-Process powershell -Verb RunAs -ArgumentList '-ExecutionPolicy Bypass -File \"%~dp0register_app.ps1\"'"
timeout /t 5

REM Build the application
echo Building with PyInstaller...
python -m PyInstaller AutoOrganizer.spec --clean

echo Build complete!
echo Executable location: dist/Auto Organizer.exe
pause