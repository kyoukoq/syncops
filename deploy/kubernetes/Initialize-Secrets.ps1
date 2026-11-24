#Requires -Version 7.4
[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string] $Context,

    [Parameter(Mandatory)]
    [ValidatePattern('^[a-z0-9]([-a-z0-9]{0,61}[a-z0-9])?$')]
    [string] $Namespace,

    [ValidatePattern('^[a-z0-9]([-a-z0-9]{0,51}[a-z0-9])?$')]
    [string] $Release = 'syncops'
)

$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $true

$definitions = [ordered] @{
    'db-admin' = @('password')
    'db-app' = @('password')
    'api-auth' = @('admin-password', 'operator-password', 'viewer-password', 'webhook-secret')
    'mock-auth' = @('token')
}

foreach ($definition in $definitions.GetEnumerator()) {
    $name = "$Release-$($definition.Key)"
    $existing = kubectl --context $Context --namespace $Namespace get secret $name --ignore-not-found -o name
    if ($existing) {
        Write-Host "Preserved Secret $name"
        continue
    }

    $data = @{}
    foreach ($key in $definition.Value) {
        $bytes = [byte[]]::new(32)
        [System.Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
        $secret = [Convert]::ToHexString($bytes).ToLowerInvariant()
        $data[$key] = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($secret))
    }

    @{
        apiVersion = 'v1'
        kind = 'Secret'
        metadata = @{name = $name; namespace = $Namespace}
        type = 'Opaque'
        data = $data
    } | ConvertTo-Json -Depth 4 -Compress | kubectl --context $Context --namespace $Namespace create -f -
}
