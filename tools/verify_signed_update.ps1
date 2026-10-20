param(
    [string]$SdkPath = "",
    [switch]$PreflightOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$taskBase = $PSScriptRoot
$expectedCertificate = "2f0a0908f269bc039311edb58fca8863347f1e4c3a7cfaddd909991cf1f0b509"
$expectedUnsigned = "43ffc8b8d8ba2a632d3d13a5f287a4fb6a6a43bddf008122026186aa2a0197f4"
$expectedPrevious = "8cff50f9d76dbeec261ca928603277bdf540d0d0b42913bde919a82ce8d5d49f"
$expectedDatabase = "937b641c3296fb7ea381674d5854e514b7ea84d604060fcc6b52ee9890b4ed8b"
$expectedModels = "11402c11a9f2ac1ad95770ced7f5d25073c8016ba5d4fa0c33b1e943ccd797f4"
$unsignedApk = Join-Path $taskBase "DLYA_SVOIH_v0.3.134-unsigned.apk"
$previousApk = Join-Path $taskBase "DLYA_SVOIH_v0.3.133.apk"
$signedApk = Join-Path $taskBase "DLYA_SVOIH_v0.3.134.apk"
$auditPath = Join-Path $taskBase $(if ($PreflightOnly) { "pre-signature-verification.json" } else { "signed-apk-verification.json" })
$audit = [ordered]@{
    checkedAtUtc = [DateTime]::UtcNow.ToString("o")
    status = "failed"
    signatureVerified = $false
    installationOver0133Verified = $false
    favoritesPreserved = $null
    settingsPreserved = $null
    signedApk = $null
    signedApkSha256 = $null
    expectedSignerSha256 = $expectedCertificate
    error = $null
}

function Require([bool]$Condition, [string]$Message) {
    if (-not $Condition) { throw $Message }
}

function Entry-Hash($Entry) {
    Require ($null -ne $Entry) "A required APK entry is missing"
    $stream = $Entry.Open()
    $hash = [Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($hash.ComputeHash($stream))).Replace("-", "").ToLowerInvariant() }
    finally { $stream.Dispose(); $hash.Dispose() }
}

function Entry-Text($Entry) {
    Require ($null -ne $Entry) "A required APK entry is missing"
    $reader = New-Object IO.StreamReader($Entry.Open())
    try { return $reader.ReadToEnd() }
    finally { $reader.Dispose() }
}

function Signer-Hash([string]$ApkPath, [string]$Label) {
    $lines = @(& $script:taskJava -jar $script:taskSigner verify --verbose --print-certs $ApkPath 2>&1)
    $nativeStatus = $LASTEXITCODE
    $lines | Set-Content -LiteralPath (Join-Path $taskBase ($Label + "-signature.log")) -Encoding UTF8
    Require ($nativeStatus -eq 0) ($Label + " APK signature verification failed")
    $text = $lines -join [Environment]::NewLine
    $match = [regex]::Match($text, "Signer #1 certificate SHA-256 digest: ([0-9a-fA-F]{64})")
    Require ($match.Success) ($Label + " APK certificate is missing")
    Require ($text -match "Number of signers: 1") "Unexpected signer count"
    return $match.Groups[1].Value.ToLowerInvariant()
}

function Verify-Identity([string]$ApkPath, [string]$VersionName, [string]$VersionCode, [string]$Label) {
    $lines = @(& $script:taskAapt dump badging $ApkPath 2>&1)
    $nativeStatus = $LASTEXITCODE
    $lines | Set-Content -LiteralPath (Join-Path $taskBase ($Label + "-identity.log")) -Encoding UTF8
    Require ($nativeStatus -eq 0) ($Label + " APK manifest cannot be read")
    $text = $lines -join [Environment]::NewLine
    $identity = "package: name='ru.dlyasvoih.app' versionCode='" + $VersionCode + "' versionName='" + $VersionName + "'"
    Require ($text.Contains($identity)) ($Label + " APK has the wrong package/version")
    Require (-not $text.Contains("application-debuggable")) ($Label + " APK must not be debuggable")
}

$exitStatus = 1
try {
    if ([string]::IsNullOrWhiteSpace($SdkPath)) { $SdkPath = $env:ANDROID_SDK_ROOT }
    if ([string]::IsNullOrWhiteSpace($SdkPath)) { $SdkPath = $env:ANDROID_HOME }
    if ([string]::IsNullOrWhiteSpace($SdkPath)) { $SdkPath = Join-Path $env:LOCALAPPDATA "Android\Sdk" }
    $toolDirectory = Get-ChildItem -LiteralPath (Join-Path $SdkPath "build-tools") -Directory |
        Where-Object { $_.Name -match '^\d+\.\d+\.\d+$' } |
        Sort-Object { [version]$_.Name } -Descending |
        Where-Object { (Test-Path (Join-Path $_.FullName "aapt.exe")) -and (Test-Path (Join-Path $_.FullName "lib\apksigner.jar")) } |
        Select-Object -First 1
    Require ($null -ne $toolDirectory) "Android SDK Build Tools were not found"
    $script:taskSigner = Join-Path $toolDirectory.FullName "lib\apksigner.jar"
    $script:taskAapt = Join-Path $toolDirectory.FullName "aapt.exe"
    $script:taskJava = ""
    if ($env:JAVA_HOME) {
        $candidateJava = Join-Path $env:JAVA_HOME "bin\java.exe"
        if (Test-Path $candidateJava) { $script:taskJava = $candidateJava }
    }
    if (-not $script:taskJava) {
        $candidateJava = "C:\Program Files\Android\Android Studio\jbr\bin\java.exe"
        if (Test-Path $candidateJava) { $script:taskJava = $candidateJava }
    }
    if (-not $script:taskJava) { $script:taskJava = (Get-Command java.exe -ErrorAction Stop).Source }
    Require ((Get-FileHash -LiteralPath $previousApk -Algorithm SHA256).Hash.ToLowerInvariant() -eq $expectedPrevious) "Published 0.3.133 APK hash mismatch"
    Require ((Get-FileHash -LiteralPath $unsignedApk -Algorithm SHA256).Hash.ToLowerInvariant() -eq $expectedUnsigned) "Unsigned 0.3.134 APK hash mismatch"
    Verify-Identity $previousApk "0.3.133" "137" "previous"
    Verify-Identity $unsignedApk "0.3.134" "138" "unsigned"
    $previousCertificate = Signer-Hash $previousApk "previous"
    Require ($previousCertificate -eq $expectedCertificate) "Published 0.3.133 certificate differs from the pinned certificate"
    $audit["publishedSignerSha256"] = $previousCertificate
    $audit["publishedApkSha256"] = $expectedPrevious
    $audit["unsignedApkSha256"] = $expectedUnsigned

    if ($PreflightOnly) {
        $audit["status"] = "reference-and-candidate-verified-signing-pending"
    } else {
        Verify-Identity $signedApk "0.3.134" "138" "signed"
        $signedCertificate = Signer-Hash $signedApk "signed"
        Require ($signedCertificate -eq $expectedCertificate) "Signed 0.3.134 certificate differs from published 0.3.133"
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        $beforeZip = [IO.Compression.ZipFile]::OpenRead($unsignedApk)
        $afterZip = [IO.Compression.ZipFile]::OpenRead($signedApk)
        try {
            Require (@($afterZip.Entries.FullName | Select-Object -Unique).Count -eq $afterZip.Entries.Count) "Duplicate APK entries"
            foreach ($entry in $beforeZip.Entries) {
                $signedEntry = $afterZip.GetEntry($entry.FullName)
                Require ($null -ne $signedEntry) ("Signed APK lost entry: " + $entry.FullName)
                Require (($entry.Length -eq $signedEntry.Length) -and ((Entry-Hash $entry) -eq (Entry-Hash $signedEntry))) ("APK payload changed: " + $entry.FullName)
            }
            foreach ($entry in $afterZip.Entries) {
                if ($null -eq $beforeZip.GetEntry($entry.FullName)) {
                    Require ($entry.FullName -match '^META-INF/(MANIFEST\.MF|[^/]+\.(SF|RSA|DSA|EC))$') ("Unexpected new APK payload: " + $entry.FullName)
                }
            }
            Require ((Entry-Text $afterZip.GetEntry("assets/database/content-version.txt")).Trim() -eq "195") "Wrong catalog version"
            Require ((Entry-Hash $afterZip.GetEntry("assets/database/guide-v29.db")) -eq $expectedDatabase) "Full catalog database hash mismatch"
            Require ((Entry-Hash $afterZip.GetEntry("assets/viewer3d/models.json")) -eq $expectedModels) "Model manifest hash mismatch"
            $models = (Entry-Text $afterZip.GetEntry("assets/viewer3d/models.json") | ConvertFrom-Json).models
            Require (@($models).Count -eq 19) "Expected 19 offline models"
            foreach ($model in $models) {
                $modelEntry = $afterZip.GetEntry("assets/viewer3d/" + $model.file)
                Require ($null -ne $modelEntry) ("Missing model: " + $model.id)
                Require (($modelEntry.Length -eq $model.bytes) -and ((Entry-Hash $modelEntry) -eq $model.packagedSha256)) ("Model hash mismatch: " + $model.id)
            }
            $audit["originalPayloadEntriesVerified"] = $beforeZip.Entries.Count
        } finally { $beforeZip.Dispose(); $afterZip.Dispose() }
        $signedHash = (Get-FileHash -LiteralPath $signedApk -Algorithm SHA256).Hash.ToLowerInvariant()
        $audit["status"] = "signature-and-payload-verified-installation-pending"
        $audit["signatureVerified"] = $true
        $audit["signedApk"] = $signedApk
        $audit["signedApkSha256"] = $signedHash
        $audit["signedApkBytes"] = (Get-Item -LiteralPath $signedApk).Length
        $audit["packageName"] = "ru.dlyasvoih.app"
        $audit["versionName"] = "0.3.134"
        $audit["versionCode"] = 138
        $audit["contentVersion"] = 195
        $audit["catalogVerifiedByPinnedDatabaseHash"] = $true
        $audit["expectedCards"] = 1697
        $audit["expectedImages"] = 1600
        $audit["offlineModels"] = 19
        ($signedHash + "  DLYA_SVOIH_v0.3.134.apk") | Set-Content -LiteralPath ($signedApk + ".sha256") -Encoding ASCII
        Write-Host ("Signed APK SHA-256: " + $signedHash)
    }
    $exitStatus = 0
} catch {
    $audit["error"] = $_.Exception.Message
    Write-Host ("STOP: " + $audit["error"])
} finally {
    $audit | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $auditPath -Encoding UTF8
    Write-Host ("Verification result: " + $auditPath)
}
exit $exitStatus
