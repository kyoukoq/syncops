#Requires -Version 7.4
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$envPath = Join-Path $PSScriptRoot '../.env'
if (Test-Path -LiteralPath $envPath) {
    throw 'The project .env already exists. Its settings were preserved.'
}

$names = @(
    'SYNCOPS_DB_ADMIN_PASSWORD',
    'SYNCOPS_DB_PASSWORD',
    'SYNCOPS_ADMIN_PASSWORD',
    'SYNCOPS_OPERATOR_PASSWORD',
    'SYNCOPS_VIEWER_PASSWORD',
    'SYNCOPS_MOCK_TOKEN'
)
$settings = foreach ($name in $names) {
    $bytes = [byte[]]::new(32)
    [System.Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
    $secret = [Convert]::ToHexString($bytes).ToLowerInvariant()
    "$name=$secret"
}

$options = [System.IO.FileStreamOptions]::new()
$options.Mode = [System.IO.FileMode]::CreateNew
$options.Access = [System.IO.FileAccess]::Write
$options.Share = [System.IO.FileShare]::None
if (-not $IsWindows) {
    $options.UnixCreateMode = [System.IO.UnixFileMode]::UserRead -bor [System.IO.UnixFileMode]::UserWrite
}
$stream = [System.IO.File]::Open($envPath, $options)
try {
    $writer = [System.IO.StreamWriter]::new($stream)
    $writer.WriteLine(($settings -join "`n"))
    $writer.WriteLine('SYNCOPS_WEB_PORT=8080')
    $writer.Dispose()
} finally {
    $stream.Dispose()
}
Write-Host 'Generated .env. Use its admin password to sign in after Compose starts.'
