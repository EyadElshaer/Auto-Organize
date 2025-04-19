import os
import sys
import shutil
import subprocess

print("Starting build process for Auto Organizer...")

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

# Clean previous build folders if they exist
for folder in ['build', 'dist']:
    if os.path.exists(folder):
        print(f"Cleaning {folder} directory...")
        shutil.rmtree(folder)

# List all icon files that exist
icon_files_datas = ""
icon_list = ['icon.ico', 'watch.png', 'settings.png', 'logs.png', 'info.png', 'update.png']
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
    icon='icon.ico',
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