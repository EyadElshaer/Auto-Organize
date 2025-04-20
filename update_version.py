import json
import os

def read_version_info():
    with open('version.txt', 'r') as f:
        return json.load(f)

def update_version_info_txt(version_data):
    template = f'''VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={tuple(version_data['fileversion'])},
    prodvers={tuple(version_data['productversion'])},
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
        StringStruct('CompanyName', '{version_data["companyname"]}'),
        StringStruct('ProductName', '{version_data["productname"]}'),
        StringStruct('ProductVersion', '{version_data["version"]}'),
        StringStruct('FileVersion', '{version_data["version"]}'),
        StringStruct('FileDescription', '{version_data["filedescription"]}'),
        StringStruct('InternalName', '{version_data["internalname"]}'),
        StringStruct('OriginalFilename', '{version_data["originalfilename"]}')
      ])
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1252])])
  ]
)'''
    
    with open('version_info.txt', 'w') as f:
        f.write(template)

def update_version_info_py(version_data):
    template = f'''version = '{version_data["version"]}'
company_name = '{version_data["companyname"]}'
product_name = '{version_data["productname"]}'
file_description = '{version_data["filedescription"]}'
internal_name = '{version_data["internalname"]}'
original_filename = '{version_data["originalfilename"]}'
file_version = {version_data["fileversion"]}
product_version = {version_data["productversion"]}'''

    with open('version_info.py', 'w') as f:
        f.write(template)

def update_manifest_files(version_data):
    # Update package.appxmanifest and AppxManifest.xml with version info
    files = ['package.appxmanifest', 'AppxManifest.xml']
    for file in files:
        if os.path.exists(file):
            with open(file, 'r') as f:
                content = f.read()
            
            # Update version attributes
            content = content.replace('Version="[0-9]+\\.[0-9]+\\.[0-9]+"', f'Version="{version_data["version"]}"')
            
            with open(file, 'w') as f:
                f.write(content)

def main():
    version_data = read_version_info()
    update_version_info_txt(version_data)
    update_version_info_py(version_data)
    update_manifest_files(version_data)

if __name__ == '__main__':
    main() 