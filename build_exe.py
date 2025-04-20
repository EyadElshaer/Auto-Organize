import os
import sys
import shutil
import subprocess
import time

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

# Check for required modules and install if missing
required_packages = ['PyQt5', 'pywin32', 'winshell', 'pyinstaller']
for package in required_packages:
    print(f"Checking for {package}...")
    try:
        __import__(package.lower().replace('-', '_'))
        print(f"✓ {package} is installed")
    except ImportError:
        print(f"✗ {package} is not installed. Installing...")
        try:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', package])
            print(f"✓ {package} installed successfully")
        except Exception as e:
            print(f"✗ Failed to install {package}: {str(e)}")
            input("Press Enter to exit...")
            sys.exit(1)

# Now import PyInstaller after ensuring it's installed
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

# List all icon files that exist
icon_files_datas = ""
icon_list = ['icon.ico', 'icons/watch.png', 'icons/settings.png', 'icons/logs.png', 'icons/info.png', 'icons/update.png']
for icon in icon_list:
    if os.path.exists(icon):
        print(f"Found icon: {icon}")
        icon_files_datas += f"        ('{icon}', '.'),\n"
    else:
        print(f"Icon not found: {icon}")

# Create a spec file with explicit icon paths
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
    hiddenimports=['win32com.client', 'winshell', 'urllib.request', 'json', 're', 'webbrowser', 'datetime'],
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
)
""" % icon_files_datas

with open('auto_organizer.spec', 'w') as spec_file:
    spec_file.write(spec_content)
print("Created PyInstaller spec file with the following icons:")
print(icon_files_datas)

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

print("Build completed!")
print("Executable location: dist/Auto Organizer.exe")

# Create a basic README file with instructions
readme_content = """# Auto Organizer

A tool for automatically organizing files based on naming patterns.

## Features
- Automatically move files between folders based on naming patterns
- Dark and light theme support
- System tray integration
- Persistent logs with undo/redo functionality
- Export logs with date filtering

## Installation
Simply download and run the executable. No installation required.

## Usage
1. Open the application
2. Add watch and target folder pairs
3. Click Start to begin watching
4. Files in the watch folders will be organized into subfolders in the target folders

## Support
For issues or feature requests, please visit:
https://github.com/EyadElshaer/Auto-Organize

"""

with open('README.md', 'w') as readme_file:
    readme_file.write(readme_content)
print("Created README.md file")

print("Build process completed successfully!")
input("Press Enter to exit...")