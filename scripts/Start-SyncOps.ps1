#Requires -Version 7.4
[CmdletBinding()]
param(
    [string] $PythonPath,
    [switch] $SkipInstall
)

$ErrorActionPreference = 'Stop'
$rootPath = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$statePath = Join-Path $rootPath '.syncops'
$backendPath = Join-Path $rootPath 'backend'
$frontendPath = Join-Path $rootPath 'frontend'
$venvPath = Join-Path $rootPath '.venv'
$python = Join-Path $venvPath 'Scripts/python.exe'
$credentialsPath = Join-Path $statePath 'credentials.json'
$databasePath = Join-Path $statePath 'syncops.db'
$logPath = Join-Path $statePath 'logs'
$services = [System.Collections.Generic.List[System.Diagnostics.Process]]::new()

function Invoke-Checked {
    param([string] $Executable, [string[]] $Arguments)
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$(Split-Path -Leaf $Executable) exited with code $LASTEXITCODE."
    }
}

function New-LocalSecret {
    $bytes = [byte[]]::new(32)
    [System.Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
    [Convert]::ToHexString($bytes).ToLowerInvariant()
}

function Start-ServiceProcess {
    param(
        [string] $Name,
        [string] $Executable,
        [string[]] $Arguments,
        [string] $Directory,
        [hashtable] $Environment = @{}
    )
    $process = Start-Process -FilePath $Executable -ArgumentList $Arguments `
        -WorkingDirectory $Directory -Environment $Environment -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $logPath "$Name.out.log") `
        -RedirectStandardError (Join-Path $logPath "$Name.err.log")
    $services.Add($process)
    $process
}

function Wait-ForHttp {
    param([System.Diagnostics.Process] $Process, [string] $Uri, [string] $Name)
    $deadline = [DateTime]::UtcNow.AddSeconds(25)
    while ([DateTime]::UtcNow -lt $deadline) {
        if ($Process.HasExited) {
            throw "$Name exited. Check its logs in $logPath."
        }
        try {
            $probe = Invoke-WebRequest -Uri $Uri -TimeoutSec 2 -NoProxy -SkipHttpErrorCheck
            if ($probe.StatusCode -eq 200) {
                return
            }
        } catch {
            # The listener may still be starting.
        }
        Start-Sleep -Milliseconds 250
    }
    throw "$Name did not become ready. Check its logs in $logPath."
}

New-Item -ItemType Directory -Path $statePath, $logPath -Force | Out-Null
$startupLock = [System.IO.File]::Open((Join-Path $statePath 'native.lock'), 'OpenOrCreate', 'ReadWrite', 'None')
try {
    foreach ($port in 5173, 8000, 8001) {
        $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $port)
        try {
            $listener.ExclusiveAddressUse = $true
            $listener.Start()
        } catch {
            throw "Local port $port is unavailable. Stop the service using this port and run again."
        } finally {
            $listener.Stop()
        }
    }

    if (-not (Test-Path -LiteralPath $python)) {
        if ($SkipInstall) {
            throw 'The project Python environment is missing. Start once without -SkipInstall.'
        }
        if (-not $PythonPath) {
            $installed = Get-Command python.exe -ErrorAction SilentlyContinue
            if ($installed -and $installed.Source -notmatch '[\\/]Microsoft[\\/]WindowsApps[\\/]') {
                $PythonPath = $installed.Source
            } else {
                $bundled = Join-Path ([Environment]::GetFolderPath('UserProfile')) `
                    '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
                if (Test-Path -LiteralPath $bundled) {
                    $PythonPath = $bundled
                }
            }
        }
        if (-not $PythonPath) {
            throw 'Python 3.12 is required. Supply its executable through -PythonPath.'
        }
        Invoke-Checked $PythonPath @('-c', 'import sys; sys.exit(sys.version_info[:2] != (3, 12))')
        Invoke-Checked $PythonPath @('-m', 'venv', $venvPath)
    }

    $node = (Get-Command node.exe -ErrorAction Stop).Source
    $npm = (Get-Command npm.cmd -ErrorAction Stop).Source
    if (-not $SkipInstall) {
        $previousCachePath = $env:PIP_CACHE_DIR
        try {
            $env:PIP_CACHE_DIR = Join-Path $venvPath 'pip-cache'
            Invoke-Checked $python @('-m', 'pip', 'install', '--disable-pip-version-check', '-r', (Join-Path $backendPath 'requirements.txt'))
        } finally {
            $env:PIP_CACHE_DIR = $previousCachePath
        }
        Push-Location -LiteralPath $frontendPath
        try {
            Invoke-Checked $npm @('ci', '--no-audit', '--no-fund', '--cache', (Join-Path $statePath 'npm-cache'))
        } finally {
            Pop-Location
        }
    }
    if (-not (Test-Path -LiteralPath (Join-Path $frontendPath 'node_modules/vite/bin/vite.js'))) {
        throw 'Frontend dependencies are missing. Start once without -SkipInstall.'
    }

    if (-not (Test-Path -LiteralPath $credentialsPath)) {
        if (Test-Path -LiteralPath $databasePath) {
            throw "An existing database has no matching credentials file. Restore $credentialsPath for this database."
        }
        [ordered] @{
            admin = New-LocalSecret
            operator = New-LocalSecret
            viewer = New-LocalSecret
            mock_token = New-LocalSecret
        } | ConvertTo-Json | Set-Content -LiteralPath $credentialsPath
    }
    $credentials = Get-Content -Raw -LiteralPath $credentialsPath | ConvertFrom-Json
    $databaseUrl = "sqlite+pysqlite:///$($databasePath.Replace('\', '/'))"

    $migration = Start-Process -FilePath $python -ArgumentList @('-m', 'alembic', 'upgrade', 'head') `
        -WorkingDirectory $backendPath -Environment @{ SYNCOPS_DATABASE_URL = $databaseUrl } `
        -WindowStyle Hidden -Wait -PassThru -RedirectStandardOutput (Join-Path $logPath 'migration.out.log') `
        -RedirectStandardError (Join-Path $logPath 'migration.err.log')
    if ($migration.ExitCode -ne 0) {
        throw "Database migration failed. Check the migration logs in $logPath."
    }

    $mock = Start-ServiceProcess 'mock' $python @('-m', 'uvicorn', 'syncops.mock:app', '--host', '127.0.0.1', '--port', '8001', '--no-access-log') $backendPath @{
        SYNCOPS_DATABASE_URL = $databaseUrl
        SYNCOPS_MOCK_TOKEN = $credentials.mock_token
    }
    $api = Start-ServiceProcess 'api' $python @('-m', 'uvicorn', 'syncops.api:app', '--host', '127.0.0.1', '--port', '8000', '--no-access-log') $backendPath @{
        SYNCOPS_DATABASE_URL = $databaseUrl
        SYNCOPS_ADMIN_PASSWORD = $credentials.admin
        SYNCOPS_OPERATOR_PASSWORD = $credentials.operator
        SYNCOPS_VIEWER_PASSWORD = $credentials.viewer
    }
    Wait-ForHttp $mock 'http://127.0.0.1:8001/readyz' 'Mock service'
    Wait-ForHttp $api 'http://127.0.0.1:8000/readyz' 'API'
    $null = Start-ServiceProcess 'worker' $python @('-m', 'syncops.worker') $backendPath @{
        SYNCOPS_DATABASE_URL = $databaseUrl
        SYNCOPS_MOCK_BASE_URL = 'http://127.0.0.1:8001'
        SYNCOPS_MOCK_TOKEN = $credentials.mock_token
    }
    $web = Start-ServiceProcess 'web' $node @('node_modules/vite/bin/vite.js', '--host', '127.0.0.1', '--port', '5173', '--strictPort') $frontendPath
    Wait-ForHttp $web 'http://127.0.0.1:5173/' 'Web frontend'

    Write-Host 'SyncOps is running at http://127.0.0.1:5173/.'
    Write-Host "Local demo credentials are stored in $credentialsPath. Press Ctrl+C to stop."
    while ($true) {
        foreach ($process in $services) {
            if ($process.HasExited) {
                throw "A SyncOps service exited. Check the logs in $logPath."
            }
        }
        Start-Sleep -Seconds 1
    }
} finally {
    for ($index = $services.Count - 1; $index -ge 0; $index--) {
        $process = $services[$index]
        if (-not $process.HasExited) {
            $process.Kill($true)
            $null = $process.WaitForExit(5000)
        }
        $process.Dispose()
    }
    $startupLock.Dispose()
}
