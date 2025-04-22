import os
import sys
import shutil
import subprocess
import time
from pathlib import Path

print("Starting build process for Auto Organizer...")

def create_self_signed_cert():
    """Create a self-signed certificate for code signing if it doesn't exist"""
    try:
        # Check if certificate exists
        cert_name = "AutoOrganizerCert"
        cert_path = os.path.expanduser(f"~/{cert_name}.pfx")
        
        if not os.path.exists(cert_path):
            print("Creating self-signed certificate...")
            # Create certificate using PowerShell
            ps_command = f"""
            $cert = New-SelfSignedCertificate -Type Custom -Subject "CN=Auto Organizer" -TextExtension @("2.5.29.37={{text}}1.3.6.1.5.5.7.3.3") -KeyUsage DigitalSignature -KeyAlgorithm RSA -KeyLength 2048 -NotAfter (Get-Date).AddYears(5) -CertStoreLocation "Cert:\\CurrentUser\\My"
            $password = ConvertTo-SecureString -String "AutoOrganizer123!" -Force -AsPlainText
            Export-PfxCertificate -Cert $cert -FilePath "{cert_path}" -Password $password
            """
            
            with open("create_cert.ps1", "w") as f:
                f.write(ps_command)
                
            # Run PowerShell script to create certificate
            subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", "create_cert.ps1"], 
                         capture_output=True)
            
            # Clean up
            if os.path.exists("create_cert.ps1"):
                os.remove("create_cert.ps1")
                
            print(f"Created self-signed certificate at: {cert_path}")
        return cert_path
    except Exception as e:
        print(f"Failed to create certificate: {str(e)}")
        return None

# Create self-signed certificate
cert_path = create_self_signed_cert()

# Install required packages using pip
def install_requirements():
    # First, upgrade pip itself
    try:
        print("Upgrading pip...")
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', '--upgrade', 'pip'])
    except Exception as e:
        print(f"Warning: Could not upgrade pip: {str(e)}")

    # Install packages in order of dependency
    requirements = [
        ('wheel', 'wheel'),  # Required for building some packages
        ('setuptools', 'setuptools>=65.5.1'),  # Required for building some packages
        ('PyQt5-sip', 'PyQt5-sip>=12.11'),  # Required by PyQt5
        ('PyQt5', 'PyQt5>=5.15.9'),
        ('pywin32', 'pywin32'),  # Let pip choose the best version
        ('winshell', 'winshell>=0.6'),
        ('watchdog', 'watchdog>=3.0.0'),
        ('Pillow', 'Pillow>=10.2.0'),
        ('pyinstaller-hooks-contrib', 'pyinstaller-hooks-contrib>=2024.0'),
        ('pyinstaller', 'pyinstaller>=6.3.0')
    ]
    
    print("\nInstalling required packages...")
    for package_name, package_spec in requirements:
        try:
            print(f"\nInstalling {package_spec}...")
            
            # Try to uninstall first if it exists
            try:
                subprocess.check_call([sys.executable, '-m', 'pip', 'uninstall', package_name, '-y'])
                print(f"Uninstalled existing {package_name}")
            except:
                pass  # Ignore if package wasn't installed
                
            # Install the package
            install_cmd = [sys.executable, '-m', 'pip', 'install', 
                         '--no-cache-dir', '--upgrade', package_spec]
            
            result = subprocess.run(install_cmd, 
                                 capture_output=True, 
                                 text=True)
            
            if result.returncode != 0:
                print(f"Error output: {result.stderr}")
                raise Exception(f"Installation failed with code {result.returncode}")
                
            print(f"✓ {package_spec} installed successfully")
            
        except Exception as e:
            print(f"✗ Failed to install {package_spec}")
            print(f"Error: {str(e)}")
            print("\nDetailed error information:")
            print("You can try installing this package manually using:")
            print(f"pip install {package_spec}")
            return False
            
    return True

# Install requirements
if not install_requirements():
    input("Failed to install requirements. Press Enter to exit...")
    sys.exit(1)

# Import PyInstaller after ensuring it's installed
import PyInstaller.__main__

# Ensure version.txt exists
if not os.path.exists('version.txt'):
    with open('version.txt', 'w') as f:
        f.write('v1.0.0')
    print("Created version.txt file with default version v1.0.0")

# Function to safely remove a directory with retries
def safe_remove_directory(directory, max_retries=3, delay=1):
    if not os.path.exists(directory):
        return True
        
    for attempt in range(max_retries):
        try:
            print(f"Attempting to remove {directory} (attempt {attempt + 1}/{max_retries})...")
            shutil.rmtree(directory, ignore_errors=True)
            if not os.path.exists(directory):
                return True
        except Exception as e:
            print(f"Failed to remove {directory}: {str(e)}")
        
        # Wait before retrying
        if attempt < max_retries - 1:
            print(f"Waiting {delay} seconds before retrying...")
            time.sleep(delay)
            
    return False

# Clean previous build folders if they exist
for folder in ['build', 'dist']:
    if os.path.exists(folder):
        print(f"Cleaning {folder} directory...")
        if not safe_remove_directory(folder):
            print(f"Warning: Could not completely remove {folder} directory.")
            print("Continuing with build process anyway...")

# Create Windows Defender exclusion script
def create_defender_exclusion_script():
    script_content = """
param([string]$AppPath)

# Check if running as administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Warning "This script requires administrator privileges."
    exit 1
}

try {
    # Add exclusion for the application
    Add-MpPreference -ExclusionPath $AppPath -ErrorAction Stop
    Write-Host "Successfully added Windows Defender exclusion for: $AppPath"
} catch {
    Write-Warning "Failed to add Windows Defender exclusion: $_"
    exit 1
}
"""
    
    with open('add_defender_exclusion.ps1', 'w') as f:
        f.write(script_content)
    print("Created Windows Defender exclusion script")

# List all icon files that exist
icon_files_datas = ""
icon_list = ['icon.ico', 'icons/watch.png', 'icons/settings.png', 'icons/logs.png', 'icons/info.png', 'icons/update.png']
for icon in icon_list:
    if os.path.exists(icon):
        print(f"Found icon: {icon}")
        icon_files_datas += f"        ('{icon}', '.'),\n"
    else:
        print(f"Icon not found: {icon}")

# Create a spec file with explicit icon paths and additional data files
spec_content = """
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['watcher_app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('version.txt', '.'),
%s
    ],
    hiddenimports=[
        'win32com.client',
        'winshell',
        'urllib.request',
        'json',
        're',
        'webbrowser',
        'datetime',
        'watchdog.observers',
        'watchdog.events'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Auto Organizer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icons/icon.ico',
    version='version_info.txt',
    uac_admin=True
)
""" % icon_files_datas

# Create version info file
version_info = """
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=(1, 0, 0, 0),
    prodvers=(1, 0, 0, 0),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        u'040904B0',
        [StringStruct(u'CompanyName', u'Eyad Elshaer'),
         StringStruct(u'FileDescription', u'Auto Organizer'),
         StringStruct(u'FileVersion', u'1.0.0'),
         StringStruct(u'InternalName', u'Auto Organizer'),
         StringStruct(u'LegalCopyright', u'© 2024 Eyad Elshaer'),
         StringStruct(u'OriginalFilename', u'Auto Organizer.exe'),
         StringStruct(u'ProductName', u'Auto Organizer'),
         StringStruct(u'ProductVersion', u'1.0.0')])
    ]),
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
"""

with open('auto_organizer.spec', 'w') as spec_file:
    spec_file.write(spec_content)
print("Created PyInstaller spec file")

with open('version_info.txt', 'w') as ver_file:
    ver_file.write(version_info)
print("Created version info file")

# Create Windows Defender exclusion script
create_defender_exclusion_script()

# Build executable with verbose output
print("Building executable with PyInstaller...")
try:
    PyInstaller.__main__.run([
        'auto_organizer.spec',
        '--clean',
        '--log-level', 'DEBUG'
    ])
    print("PyInstaller build completed successfully!")
except Exception as e:
    print(f"PyInstaller build failed: {str(e)}")
    input("Press Enter to exit...")
    sys.exit(1)

# Sign the executable if certificate is available
if cert_path and os.path.exists(cert_path):
    exe_path = os.path.join("dist", "Auto Organizer.exe")
    if os.path.exists(exe_path):
        print("Signing the executable...")
        try:
            # Sign using signtool
            sign_command = [
                "signtool", "sign",
                "/f", cert_path,
                "/p", "AutoOrganizer123!",
                "/tr", "http://timestamp.digicert.com",
                "/td", "sha256",
                "/fd", "sha256",
                exe_path
            ]
            subprocess.run(sign_command, check=True)
            print("Successfully signed the executable!")
        except Exception as e:
            print(f"Failed to sign executable: {str(e)}")
    else:
        print("Executable not found for signing")

# Build the installer using Inno Setup
print("\nBuilding installer with Inno Setup...")
try:
    # Check if Inno Setup is installed
    iscc_path = None
    possible_paths = [
        r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        r"C:\Program Files\Inno Setup 6\ISCC.exe"
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            iscc_path = path
            break
    
    if iscc_path is None:
        print("Inno Setup not found. Please install Inno Setup 6 from https://jrsoftware.org/isdl.php")
        input("Press Enter to exit...")
        sys.exit(1)
    
    # Run Inno Setup Compiler
    subprocess.run([iscc_path, "installer.iss"], check=True)
    print("Installer built successfully!")
    
    # Get the installer path
    installer_path = os.path.abspath("AutoOrganizerSetup.exe")
    
    # Sign the installer if certificate is available
    if cert_path and os.path.exists(cert_path):
        print("Signing the installer...")
        try:
            sign_command = [
                "signtool", "sign",
                "/f", cert_path,
                "/p", "AutoOrganizer123!",
                "/tr", "http://timestamp.digicert.com",
                "/td", "sha256",
                "/fd", "sha256",
                installer_path
            ]
            subprocess.run(sign_command, check=True)
            print("Successfully signed the installer!")
        except Exception as e:
            print(f"Failed to sign installer: {str(e)}")
    
except Exception as e:
    print(f"Failed to build installer: {str(e)}")
    input("Press Enter to exit...")
    sys.exit(1)

print("\nBuild process completed!")
print(f"Installer location: {os.path.abspath('AutoOrganizerSetup.exe')}")
print("\nTo distribute the application:")
print("1. Share the AutoOrganizerSetup.exe file with users")
print("2. Users can run the installer to install the application")
print("3. The application can be uninstalled through Windows Settings")
input("Press Enter to exit...")