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

REM Create vcredist directory if it doesn't exist
if not exist "vcredist" mkdir vcredist

REM Download Visual C++ Redistributable if not exists
if not exist "vcredist\VC_redist.x64.exe" (
    echo Downloading Visual C++ Redistributable...
    powershell -Command "& {Invoke-WebRequest -Uri 'https://aka.ms/vs/17/release/vc_redist.x64.exe' -OutFile 'vcredist\VC_redist.x64.exe'}"
    if not exist "vcredist\VC_redist.x64.exe" (
        echo Failed to download Visual C++ Redistributable.
        echo Please download it manually from:
        echo https://aka.ms/vs/17/release/vc_redist.x64.exe
        echo and place it in the vcredist folder.
        pause
        exit /b 1
    )
)

REM Check for signtool.exe in common locations
set "SIGNTOOL_PATH="
for %%p in (
    "C:\Program Files (x86)\Windows Kits\10\bin\10.0.22621.0\x64\signtool.exe"
    "C:\Program Files (x86)\Windows Kits\10\bin\10.0.22000.0\x64\signtool.exe"
    "C:\Program Files (x86)\Windows Kits\10\bin\10.0.19041.0\x64\signtool.exe"
    "C:\Program Files (x86)\Windows Kits\10\bin\10.0.18362.0\x64\signtool.exe"
    "C:\Program Files (x86)\Windows Kits\10\bin\10.0.17763.0\x64\signtool.exe"
    "C:\Program Files (x86)\Windows Kits\10\bin\10.0.17134.0\x64\signtool.exe"
    "C:\Program Files (x86)\Windows Kits\10\bin\10.0.16299.0\x64\signtool.exe"
    "C:\Program Files (x86)\Windows Kits\10\bin\x64\signtool.exe"
    "C:\Program Files (x86)\Windows Kits\10\App Certification Kit\signtool.exe"
) do (
    if exist %%p (
        set "SIGNTOOL_PATH=%%p"
        echo Found signtool at: %%p
        goto :found_signtool
    )
)

:check_signtool
where signtool >nul 2>nul
if %ERRORLEVEL% equ 0 (
    set "SIGNTOOL_PATH=signtool"
    goto :found_signtool
)

echo WARNING: signtool.exe not found. Code signing will be skipped.
echo To enable code signing, please install the Windows SDK from:
echo https://developer.microsoft.com/en-us/windows/downloads/windows-sdk/
echo.
echo After installation, modify this build script to point to your signtool.exe location by editing
echo the SIGNTOOL_PATH variable in this file. For example:
echo set "SIGNTOOL_PATH=C:\Path\to\your\signtool.exe"
echo.
set "SKIP_SIGNING=1"
goto :continue_build

:found_signtool
set "SKIP_SIGNING=0"

:continue_build
REM Install required packages
echo Installing required packages...
python -m pip install --upgrade pip
python -m pip install --upgrade wheel setuptools PyQt5-sip PyQt5 pywin32 winshell watchdog Pillow pyinstaller-hooks-contrib pyinstaller

REM Clean up previous build artifacts
echo Cleaning up previous builds...
if exist "build" rd /s /q "build"
if exist "dist" rd /s /q "dist"
if exist "__pycache__" rd /s /q "__pycache__"
if exist "*.spec" del /f /q "*.spec"

REM Create version info file
echo Creating version info file...
echo VSVersionInfo( > version_info.txt
echo   ffi=FixedFileInfo( >> version_info.txt
echo     filevers=(1, 0, 0, 0^), >> version_info.txt
echo     prodvers=(1, 0, 0, 0^), >> version_info.txt
echo     mask=0x3f, >> version_info.txt
echo     flags=0x0, >> version_info.txt
echo     OS=0x40004, >> version_info.txt
echo     fileType=0x1, >> version_info.txt
echo     subtype=0x0, >> version_info.txt
echo     date=(0, 0^) >> version_info.txt
echo   ^), >> version_info.txt
echo   kids=[ >> version_info.txt
echo     StringFileInfo([ >> version_info.txt
echo       StringTable( >> version_info.txt
echo         u'040904B0', >> version_info.txt
echo         [StringStruct(u'CompanyName', u'Eyad Elshaer'^), >> version_info.txt
echo          StringStruct(u'FileDescription', u'Auto Organizer'^), >> version_info.txt
echo          StringStruct(u'FileVersion', u'1.0.0'^), >> version_info.txt
echo          StringStruct(u'InternalName', u'Auto Organizer'^), >> version_info.txt
echo          StringStruct(u'LegalCopyright', u'(c) 2024 Eyad Elshaer'^), >> version_info.txt
echo          StringStruct(u'OriginalFilename', u'Auto Organizer.exe'^), >> version_info.txt
echo          StringStruct(u'ProductName', u'Auto Organizer'^), >> version_info.txt
echo          StringStruct(u'ProductVersion', u'1.0.0'^)]^) >> version_info.txt
echo     ]^), >> version_info.txt
echo     VarFileInfo([VarStruct(u'Translation', [1033, 1200]^)]^) >> version_info.txt
echo   ] >> version_info.txt
echo ^) >> version_info.txt

REM Create PyInstaller spec file
echo Creating PyInstaller spec file...
python -m PyInstaller --name="Auto Organizer" ^
    --onefile ^
    --windowed ^
    --icon=icons/icon.ico ^
    --add-data="version.txt;." ^
    --add-data="icons/*;icons" ^
    --hidden-import=win32com.client ^
    --hidden-import=winshell ^
    --hidden-import=urllib.request ^
    --hidden-import=json ^
    --hidden-import=re ^
    --hidden-import=webbrowser ^
    --hidden-import=datetime ^
    --hidden-import=watchdog.observers ^
    --hidden-import=watchdog.events ^
    --version-file=version_info.txt ^
    --uac-admin ^
    watcher_app.py

REM Build the application
echo Building with PyInstaller...
python -m PyInstaller --clean "Auto Organizer.spec"

if "%SKIP_SIGNING%"=="0" (
    REM Create self-signed certificate if needed
    echo Creating self-signed certificate if needed...
    if not exist "%USERPROFILE%\AutoOrganizerCert.pfx" (
        powershell -Command "$cert = New-SelfSignedCertificate -Type Custom -Subject 'CN=Auto Organizer' -TextExtension @('2.5.29.37={text}1.3.6.1.5.5.7.3.3') -KeyUsage DigitalSignature -KeyAlgorithm RSA -KeyLength 2048 -NotAfter (Get-Date).AddYears(5) -CertStoreLocation 'Cert:\CurrentUser\My'; $password = ConvertTo-SecureString -String 'AutoOrganizer123!' -Force -AsPlainText; Export-PfxCertificate -Cert $cert -FilePath '$env:USERPROFILE\AutoOrganizerCert.pfx' -Password $password"
    )

    REM Sign the executable
    echo Signing the executable...
    "%SIGNTOOL_PATH%" sign /f "%USERPROFILE%\AutoOrganizerCert.pfx" /p "AutoOrganizer123!" /tr http://timestamp.digicert.com /td sha256 /fd sha256 "dist\Auto Organizer.exe"
)

REM Build Inno Setup installer
echo Building installer with Inno Setup...
set "INNO_FOUND=0"
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" (
    echo Using Inno Setup from: C:\Program Files (x86)\Inno Setup 6\ISCC.exe
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
    if %ERRORLEVEL% neq 0 (
        echo Error: Inno Setup compilation failed with code %ERRORLEVEL%.
        echo Attempting to fix common errors in installer script...
        
        REM Create a temporary fixed version of the installer script
        powershell -Command "(Get-Content installer.iss) -replace 'Check: not IsAdminLoggedOn', '' | Set-Content installer_temp.iss"
        
        echo Retrying with modified installer script...
        "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer_temp.iss
        
        if %ERRORLEVEL% neq 0 (
            echo Error: Inno Setup compilation still failed.
            echo Please check installer.iss for syntax errors.
        ) else (
            echo Successfully built installer using modified script.
            set "INNO_FOUND=1"
        )
        
        REM Clean up temporary file
        if exist "installer_temp.iss" del /f /q "installer_temp.iss"
    ) else (
        set "INNO_FOUND=1"
    )
) else if exist "C:\Program Files\Inno Setup 6\ISCC.exe" (
    echo Using Inno Setup from: C:\Program Files\Inno Setup 6\ISCC.exe
    "C:\Program Files\Inno Setup 6\ISCC.exe" installer.iss
    if %ERRORLEVEL% neq 0 (
        echo Error: Inno Setup compilation failed with code %ERRORLEVEL%.
        echo Attempting to fix common errors in installer script...
        
        REM Create a temporary fixed version of the installer script
        powershell -Command "(Get-Content installer.iss) -replace 'Check: not IsAdminLoggedOn', '' | Set-Content installer_temp.iss"
        
        echo Retrying with modified installer script...
        "C:\Program Files\Inno Setup 6\ISCC.exe" installer_temp.iss
        
        if %ERRORLEVEL% neq 0 (
            echo Error: Inno Setup compilation still failed.
            echo Please check installer.iss for syntax errors.
        ) else (
            echo Successfully built installer using modified script.
            set "INNO_FOUND=1"
        )
        
        REM Clean up temporary file
        if exist "installer_temp.iss" del /f /q "installer_temp.iss"
    ) else (
        set "INNO_FOUND=1"
    )
)

if "%INNO_FOUND%"=="0" (
    echo Inno Setup not found or compilation failed. 
    echo Please install Inno Setup 6 from: https://jrsoftware.org/isdl.php
    echo.
    echo If Inno Setup is already installed, check installer.iss for errors.
    goto :end
)

if "%SKIP_SIGNING%"=="0" (
    REM Sign the installer
    echo Signing the installer...
    "%SIGNTOOL_PATH%" sign /f "%USERPROFILE%\AutoOrganizerCert.pfx" /p "AutoOrganizer123!" /tr http://timestamp.digicert.com /td sha256 /fd sha256 "AutoOrganizerSetup.exe"
)

:end
echo Build process completed!
if exist "AutoOrganizerSetup.exe" (
    echo Installer location: %CD%\AutoOrganizerSetup.exe
) else (
    echo Note: Installer was not created. Please check the errors above.
)
pause