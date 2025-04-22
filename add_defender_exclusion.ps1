# Get the path from command line argument
param([string]$ExePath)

# Check if running as administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "This script requires administrator privileges."
    exit 1
}

try {
    # Add the exclusion
    Add-MpPreference -ExclusionPath $ExePath -ErrorAction Stop
    
    # Verify the exclusion was added
    $exclusions = Get-MpPreference | Select-Object -ExpandProperty ExclusionPath
    if ($exclusions -contains $ExePath) {
        Write-Host "Successfully added exclusion for: $ExePath"
        exit 0
    } else {
        Write-Host "Failed to verify exclusion was added."
        exit 1
    }
} catch {
    Write-Host "Error adding exclusion: $_"
    exit 1
}
