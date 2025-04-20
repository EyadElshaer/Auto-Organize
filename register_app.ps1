# Self-elevate if not already running as administrator
if (-NOT ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {   
    $arguments = "& '" + $myinvocation.mycommand.definition + "'"
    Start-Process powershell -Verb runAs -ArgumentList $arguments
    Exit
}

# Application details
$appName = "Auto Organizer"
$appId = "AutoOrganizer.Application"
$publisher = "CN=Eyad Elshaer"
$version = "1.0.3.0"
$installPath = Split-Path -Parent $PSCommandPath

Write-Host "Registering application..."

# First try HKCU for user-specific settings
try {
    $userKey = "HKCU:\Software\Auto Organizer"
    if (!(Test-Path $userKey)) {
        New-Item -Path $userKey -Force | Out-Null
    }
    Set-ItemProperty -Path $userKey -Name "InstallPath" -Value $installPath -ErrorAction Stop
    Set-ItemProperty -Path $userKey -Name "Version" -Value $version -ErrorAction Stop
    Write-Host "User settings registered successfully"
} catch {
    Write-Host "Warning: Could not register user settings: $_"
}

# Then handle HKLM registrations that require admin rights
try {
    # Enable development mode
    $developmentKey = "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\AppModelUnlock"
    if (!(Test-Path $developmentKey)) {
        New-Item -Path $developmentKey -Force | Out-Null
    }
    Set-ItemProperty -Path $developmentKey -Name "AllowDevelopmentWithoutDevLicense" -Value 1 -Type DWord -ErrorAction Stop

    # Register package identity
    $packageKey = "HKLM:\SOFTWARE\Classes\Local Settings\Software\Microsoft\Windows\CurrentVersion\AppModel\Repository\Packages\AutoOrganizer_$version"
    if (!(Test-Path $packageKey)) {
        New-Item -Path $packageKey -Force | Out-Null
    }
    Set-ItemProperty -Path $packageKey -Name "PackageRootFolder" -Value $installPath -ErrorAction Stop
    Set-ItemProperty -Path $packageKey -Name "PackageID" -Value $appId -ErrorAction Stop
    Set-ItemProperty -Path $packageKey -Name "Publisher" -Value $publisher -ErrorAction Stop

    # Register application path
    $appPathKey = "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\Auto Organizer.exe"
    if (!(Test-Path $appPathKey)) {
        New-Item -Path $appPathKey -Force | Out-Null
    }
    Set-ItemProperty -Path $appPathKey -Name "(Default)" -Value "$installPath\Auto Organizer.exe" -ErrorAction Stop
    Set-ItemProperty -Path $appPathKey -Name "Path" -Value $installPath -ErrorAction Stop

    Write-Host "System settings registered successfully"
} catch {
    Write-Host "Warning: Some system settings could not be registered: $_"
    Write-Host "The application may still work but with limited functionality"
}

# Register application path with Windows Defender
$appPath = Join-Path $PSScriptRoot "dist\AutoOrganizer.exe"
$buildPath = Join-Path $PSScriptRoot "build"
$distPath = Join-Path $PSScriptRoot "dist"

# Add exclusions for build process
Add-MpPreference -ExclusionPath $PSScriptRoot
Add-MpPreference -ExclusionPath $buildPath
Add-MpPreference -ExclusionPath $distPath
Add-MpPreference -ExclusionProcess "python.exe"
Add-MpPreference -ExclusionProcess "pythonw.exe"

# Register application capabilities
$registryPath = "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\AppCompatFlags\Layers"
$registryValue = "~ RUNASADMIN GDIPIXELFORMAT WINXPSP3"

# Create registry key if it doesn't exist
if (-not (Test-Path $registryPath)) {
    New-Item -Path $registryPath -Force
}

# Set application compatibility flags
Set-ItemProperty -Path $registryPath -Name $appPath -Value $registryValue -Type String

Write-Host "Application registered successfully with Windows security."

Write-Host "Registration complete!"