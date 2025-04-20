# This script adds the Auto Organizer executable to Windows Defender exclusions
param (
    [Parameter(Mandatory=$true)]
    [string]$AppPath
)

# Check if running with administrator privileges
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-Not $isAdmin) {
    Write-Error "This script must be run with administrator privileges."
    exit 1
}

try {
    # Check if Windows Defender is running
    $defenderService = Get-Service -Name WinDefend -ErrorAction SilentlyContinue
    
    if ($defenderService -and $defenderService.Status -eq "Running") {
        # Add the application to exclusions
        Add-MpPreference -ExclusionPath $AppPath -ErrorAction Stop
        Write-Output "Successfully added $AppPath to Windows Defender exclusions."
        exit 0
    } else {
        Write-Output "Windows Defender service is not running."
        exit 2
    }
} catch {
    Write-Error "Failed to add Windows Defender exclusion: $_"
    exit 1
}
