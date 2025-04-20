# -*- mode: python ; coding: utf-8 -*-
import re

block_cipher = None

def get_version_info():
    with open('version.txt', 'r') as f:
        version = f.read().strip()
    
    # Parse version into components
    match = re.match(r'(\d+)\.(\d+)\.(\d+)', version)
    if not match:
        raise ValueError("Invalid version format. Use X.Y.Z format")
    
    major, minor, patch = map(int, match.groups())
    version_tuple = (major, minor, patch, 0)
    
    return {
        'filevers': version_tuple,
        'prodvers': version_tuple,
        'CompanyName': 'Eyad Elshaer',
        'FileDescription': 'Auto File Organizer',
        'LegalCopyright': '© 2024 Eyad Elshaer',
        'ProductName': 'Auto Organizer',
        'ProductVersion': version
    }

a = Analysis(
    ['watcher_app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('icons/*', 'icons/'),
        ('version.txt', '.'),
        ('app.manifest', '.'),
        ('security_policy.json', '.')
    ],
    hiddenimports=['win32api', 'win32con', 'win32gui', 'win32com.client'],
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
    name='AutoOrganizer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version_info=get_version_info(),
    manifest='app.manifest',
    icon='icons/icon.ico',
    uac_admin=False
)
