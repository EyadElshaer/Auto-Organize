import re
import os

# Constants for version information
COMPANY_NAME = "Eyad Elshaer"
PRODUCT_NAME = "Auto Organizer"
FILE_DESCRIPTION = "Auto File Organizer"
INTERNAL_NAME = "AutoOrganizer"
ORIGINAL_FILENAME = "AutoOrganizer.exe"

def read_version():
    """Read the simple version number from version.txt"""
    with open('version.txt', 'r') as f:
        version = f.read().strip()
    
    # Remove 'v' prefix if present
    if version.startswith('v'):
        version = version[1:]
    
    # Parse version into components
    match = re.match(r'(\d+)\.(\d+)\.(\d+)', version)
    if not match:
        raise ValueError("Invalid version format. Use X.Y.Z or vX.Y.Z format")
    
    major, minor, patch = map(int, match.groups())
    return version, (major, minor, patch, 0)

def update_version_info_txt(version, version_tuple):
    """Update version_info.txt with version information"""
    content = f'''VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={version_tuple},
    prodvers={version_tuple},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable('040904E4', [
        StringStruct('CompanyName', '{COMPANY_NAME}'),
        StringStruct('ProductName', '{PRODUCT_NAME}'),
        StringStruct('ProductVersion', '{version}'),
        StringStruct('FileVersion', '{version}'),
        StringStruct('FileDescription', '{FILE_DESCRIPTION}'),
        StringStruct('InternalName', '{INTERNAL_NAME}'),
        StringStruct('OriginalFilename', '{ORIGINAL_FILENAME}')
      ])
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1252])])
  ]
)'''
    
    with open('version_info.txt', 'w') as f:
        f.write(content)

def update_manifest_files(version):
    """Update version in manifest files"""
    files = ['package.appxmanifest']
    for file in files:
        if os.path.exists(file):
            with open(file, 'r') as f:
                content = f.read()
            
            # Update version attributes
            content = re.sub(r'Version="[\d\.]+"', f'Version="{version}"', content)
            
            with open(file, 'w') as f:
                f.write(content)

def main():
    try:
        version, version_tuple = read_version()
        update_version_info_txt(version, version_tuple)
        update_manifest_files(version)
        print(f"Successfully updated all files to version {version}")
    except Exception as e:
        print(f"Error updating version: {str(e)}")

if __name__ == '__main__':
    main() 