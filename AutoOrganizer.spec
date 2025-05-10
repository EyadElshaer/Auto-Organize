# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

def get_version_info():
    return {
        'filevers': (1, 0, 3, 0),
        'prodvers': (1, 0, 3, 0),
        'CompanyName': 'Eyad Elshaer',
        'FileDescription': 'Auto File Organizer',
        'LegalCopyright': '© 2024 Eyad Elshaer',
        'ProductName': 'Auto Organizer',
        'ProductVersion': '1.0.3'
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
