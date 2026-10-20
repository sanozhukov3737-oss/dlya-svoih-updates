param([string]$KeystorePath = (Join-Path $env:USERPROFILE '.android\debug.keystore'))
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $KeystorePath -PathType Leaf)) {
    throw "Debug signing key not found: $KeystorePath. Run MAKE_APK.bat on this PC first, or specify -KeystorePath."
}
$keyBytes = [System.IO.File]::ReadAllBytes((Resolve-Path -LiteralPath $KeystorePath).Path)
[Convert]::ToBase64String($keyBytes) | Set-Clipboard
Write-Host 'Signing key copied to clipboard. Paste it ONLY into the GitHub Actions secret ANDROID_DEBUG_KEYSTORE_BASE64.'
Write-Host 'Do not paste the key into chat, repository files, release descriptions or public issues.'
