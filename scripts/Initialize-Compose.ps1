#Requires -Version 7.1
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

$stream = [System.IO.File]::Open($envPath, 'CreateNew', 'Write', 'None')
try {
    $writer = [System.IO.StreamWriter]::new($stream)
    $writer.WriteLine(($settings -join "`n"))
    $writer.WriteLine('SYNCOPS_WEB_PORT=8080')
    $writer.Dispose()
} finally {
    $stream.Dispose()
}
Write-Host 'Generated .env. Use its admin password to sign in after Compose starts.'
