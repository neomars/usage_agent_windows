# client/get_windows_update_status.ps1
# Output: JSON containing WSUS status and Windows Update information.

$ErrorActionPreference = "SilentlyContinue" # Continue on non-terminating errors

$output = @{
    wsusServer = "None"
    lastScanTime = $null # ISO 8601 format string or null
    pendingSecurityUpdatesCount = 0
    rebootPending = $false
    overallStatus = "Unknown" # e.g., "UpToDate", "UpdatesAvailable", "PendingReboot", "Error"
    errorMessage = $null # To capture any script-specific errors
}

try {
    # 1. Check for WSUS Server configuration
    $wsusRegistryPath = "HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate"
    $wsusServerValue = (Get-ItemProperty -Path $wsusRegistryPath -Name "WUServer" -ErrorAction SilentlyContinue).WUServer
    if ($wsusServerValue) {
        $output.wsusServer = $wsusServerValue
    }

    # 2. Initialize Windows Update COM Object
    $updateSession = New-Object -ComObject "Microsoft.Update.Session"
    $updateSearcher = $updateSession.CreateUpdateSearcher()

    # 3. Get Last Successful Scan Time
    $historyCount = $updateSearcher.QueryHistory(0, 1).Count # Get the count of history events
    if ($historyCount -gt 0) {
        $lastSearch = $updateSearcher.QueryHistory(0, 1) | Select-Object -First 1
        if ($lastSearch -and $lastSearch.Date) {
            $output.lastScanTime = ($lastSearch.Date).ToUniversalTime().ToString("o")
        }
    }

    # 4. Search for pending updates
    $searchResult = $updateSearcher.Search("IsInstalled=0 and Type='Software' and IsHidden=0")
    $updatesToInstall = $searchResult.Updates

    $securityUpdatesFound = 0
    if ($updatesToInstall.Count -gt 0) {
        foreach ($update in $updatesToInstall) {
            $isSecurityUpdate = $false
            # Iterate through categories of each update
            if ($update.Categories.Count -gt 0) {
                foreach ($category in $update.Categories) {
                    # Security Update CategoryID: '0fa1201d-4330-4fa8-8ae9-b877473b6441'
                    if ($category.CategoryID -eq '0fa1201d-4330-4fa8-8ae9-b877473b6441') {
                        $isSecurityUpdate = $true
                        break # Break from inner loop once identified as security update
                    }
                }
            }
            if ($isSecurityUpdate) {
                $securityUpdatesFound++
            }
        }
    }
    $output.pendingSecurityUpdatesCount = $securityUpdatesFound

    # 5. Check for Reboot Pending status
    $sysInfo = New-Object -ComObject "Microsoft.Update.SystemInfo"
    $output.rebootPending = $sysInfo.RebootRequired

    # 6. Determine Overall Status
    if ($output.rebootPending) {
        $output.overallStatus = "PendingReboot"
    } elseif ($output.pendingSecurityUpdatesCount -gt 0) {
        $output.overallStatus = "UpdatesAvailable" # Specifically security updates
    } elseif ($updatesToInstall.Count -gt 0) {
        $output.overallStatus = "OtherUpdatesAvailable"
    } else {
        $output.overallStatus = "UpToDate"
    }

} catch {
    $output.errorMessage = "Error in script: $($_.Exception.Message)"
    $output.overallStatus = "Error"
}

# Output the result as a compressed JSON string
Write-Output ($output | ConvertTo-Json -Compress -Depth 5)
