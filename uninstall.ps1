#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Safely uninstalls ai-cross-mem on Windows.

.DESCRIPTION
    Removes only files and configuration changes recorded by the installer.
    Saved memories are kept unless --delete-memories is explicitly requested
    and confirmed interactively.

.EXAMPLE
    .\uninstall.ps1
    .\uninstall.ps1 --delete-memories
#>

[CmdletBinding()]
param(
    [switch]$DeleteMemories
)

$pythonCmd = $null
foreach ($cmd in @("python", "python3")) {
    try {
        & $cmd --version *> $null
        if ($LASTEXITCODE -eq 0) {
            $pythonCmd = $cmd
            break
        }
    } catch {}
}

if (-not $pythonCmd) {
    Write-Error "Python 3 is required to safely uninstall ai-cross-mem."
    exit 1
}

$uninstaller = Join-Path $PSScriptRoot "uninstall.py"
if (-not (Test-Path $uninstaller)) {
    Write-Error "Uninstaller script not found: $uninstaller"
    exit 1
}

$arguments = @($uninstaller)
if ($DeleteMemories) {
    $arguments += "--delete-memories"
}
& $pythonCmd @arguments
exit $LASTEXITCODE
