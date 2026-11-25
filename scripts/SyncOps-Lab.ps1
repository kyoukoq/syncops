#Requires -Version 7.4
[CmdletBinding()]
param(
    [Parameter(Mandatory, Position = 0)]
    [ValidateSet('start', 'stop', 'status', 'urls', 'diagnose', 'demo', 'backup', 'restore-drill')]
    [string] $Action,
    [string] $Archive,
    [string] $PythonPath,
    [switch] $SkipInstall
)

$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $true
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$state = Join-Path $root '.syncops'
$database = Join-Path $state 'syncops.db'
$credentials = Join-Path $state 'credentials.json'
$venvPython = Join-Path $root '.venv/Scripts/python.exe'
$lockPath = Join-Path $state 'native.lock'

function Test-NativeLauncherActive {
    if (-not (Test-Path -LiteralPath $lockPath -PathType Leaf)) { return $false }
    try {
        $file = [IO.File]::Open($lockPath, 'Open', 'Read', 'ReadWrite')
        $file.Dispose()
        return $false
    } catch [IO.IOException] {
        return $_.Exception.HResult -in @(-2147024864, -2147024863)
    }
}

function Test-LocalUrl {
    param([string] $Uri)
    try {
        $probe = @{
            Uri = $Uri
            NoProxy = $true
            MaximumRedirection = 0
            ConnectionTimeoutSeconds = 3
            OperationTimeoutSeconds = 3
            SkipHttpErrorCheck = $true
        }
        return (Invoke-WebRequest @probe).StatusCode -eq 200
    } catch {
        return $false
    }
}

function Show-NativeUrls {
    if (-not (Test-NativeLauncherActive)) {
        Write-Host 'Unverified native URLs (the launcher does not hold its lock).'
        return $false
    }
    $available = $true
    foreach ($service in @(
        @{ Name = 'Console'; Origin = 'http://127.0.0.1:5173'; Probe = '/' }
        @{ Name = 'API'; Origin = 'http://127.0.0.1:8000'; Probe = '/readyz' }
        @{ Name = 'Mock'; Origin = 'http://127.0.0.1:8001'; Probe = '/readyz' }
    )) {
        if (Test-LocalUrl ($service.Origin + $service.Probe)) {
            Write-Host ('Verified   {0,-10} {1}' -f $service.Name, $service.Origin)
        } else {
            Write-Host ('Unverified {0,-10} (loopback health probe failed)' -f $service.Name)
            $available = $false
        }
    }
    return $available
}

function Get-LocalPython {
    if ($PythonPath) { return (Resolve-Path -LiteralPath $PythonPath).Path }
    if (Test-Path -LiteralPath $venvPython -PathType Leaf) { return $venvPython }
    throw 'The project Python environment is missing. Start the native profile or pass -PythonPath.'
}

if ($Archive -and $Action -ne 'restore-drill') {
    throw '-Archive is supported with restore-drill only.'
}

switch ($Action) {
    'start' {
        & (Join-Path $PSScriptRoot 'Start-SyncOps.ps1') -PythonPath $PythonPath -SkipInstall:$SkipInstall
    }
    'stop' {
        if (Test-NativeLauncherActive) {
            Write-Host 'Press Ctrl+C in the PowerShell window where you started SyncOps.'
        } else {
            Write-Host 'The native launcher is stopped.'
        }
    }
    'status' { $null = Show-NativeUrls }
    'urls' { if (-not (Show-NativeUrls)) { exit 1 } }
    'diagnose' {
        Write-Host "PowerShell $($PSVersionTable.PSVersion)"
        Write-Host "Node available: $([bool](Get-Command node.exe -ErrorAction SilentlyContinue))"
        Write-Host "Project Python available: $(Test-Path -LiteralPath $venvPython -PathType Leaf)"
        Write-Host "SQLite file present: $(Test-Path -LiteralPath $database -PathType Leaf)"
        Write-Host "Credential file present: $(Test-Path -LiteralPath $credentials -PathType Leaf)"
        Write-Host "Native logs directory: $(Join-Path $state 'logs')"
        $null = Show-NativeUrls
    }
    'demo' {
        if (-not (Test-NativeLauncherActive) -or -not (Test-LocalUrl 'http://127.0.0.1:8000/readyz')) {
            throw 'Start the native profile and wait for its API to become ready.'
        }
        $previous = $env:NO_PROXY
        try {
            $env:NO_PROXY = '*'
            $arguments = @('--base-url', 'http://127.0.0.1:8000', '--credentials', $credentials)
            & (Get-LocalPython) (Join-Path $PSScriptRoot 'seed_demo.py') @arguments
        } finally {
            $env:NO_PROXY = $previous
        }
    }
    { $_ -in 'backup', 'restore-drill' } {
        if ($Action -eq 'restore-drill' -and -not $Archive) { throw 'Pass -Archive followed by a SQLite backup path.' }
        $backups = Join-Path $state 'backups'
        New-Item -ItemType Directory -Path $backups -Force | Out-Null
        $stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
        $source = $database
        $name = "syncops-win-$stamp.sqlite"
        if ($Action -eq 'restore-drill') {
            $source = (Resolve-Path -LiteralPath $Archive).Path
            if ($source -eq $database) { throw 'Use an existing backup archive as the restore source.' }
            $name = "syncops-win-restore-drill-$stamp.sqlite"
        }
        $destination = Join-Path $backups $name
        & (Get-LocalPython) (Join-Path $root 'ops/sqlite_snapshot.py') $source $destination
        Write-Host "Snapshot path $destination"
    }
}
