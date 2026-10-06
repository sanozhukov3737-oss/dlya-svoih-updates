$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$wrapperJar = Join-Path $projectRoot 'gradle\wrapper\gradle-wrapper.jar'
$expectedSha = '81a82aaea5abcc8ff68b3dfcb58b3c3c429378efd98e7433460610fecd7ae45f'
try {
    $sdkCandidates = @($env:ANDROID_HOME, 'D:\Android\Sdk', 'D:\DAndroidSdk\Sdk',
        (Join-Path $env:LOCALAPPDATA 'Android\Sdk')) | Where-Object { $_ } | Select-Object -Unique
    $sdkRoot = $sdkCandidates | Where-Object {
        Test-Path -LiteralPath (Join-Path $_ 'platforms\android-36\android.jar')
    } | Select-Object -First 1
    if (-not $sdkRoot) { throw 'Android SDK Platform 36 not found.' }
    $env:ANDROID_HOME = $sdkRoot
    Remove-Item Env:ANDROID_SDK_ROOT -ErrorAction SilentlyContinue
    ('sdk.dir=' + ($sdkRoot -replace '\\', '/')) | Set-Content -LiteralPath (Join-Path $projectRoot 'local.properties') -Encoding ASCII
    if (-not (Test-Path -LiteralPath $wrapperJar)) {
        $tempJar = Join-Path (Split-Path $wrapperJar) ('wrapper-' + [Guid]::NewGuid().ToString('N') + '.tmp')
        try {
            [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
            Invoke-WebRequest -UseBasicParsing -TimeoutSec 120 -Uri 'https://raw.githubusercontent.com/gradle/gradle/v8.13.0/gradle/wrapper/gradle-wrapper.jar' -OutFile $tempJar
            if ((Get-FileHash -LiteralPath $tempJar -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expectedSha) {
                throw 'Gradle wrapper checksum mismatch'
            }
            Move-Item -LiteralPath $tempJar -Destination $wrapperJar -Force
        } finally {
            if (Test-Path -LiteralPath $tempJar) { Remove-Item -LiteralPath $tempJar -Force }
        }
    }
    if ((Get-FileHash -LiteralPath $wrapperJar -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expectedSha) {
        throw 'Gradle wrapper checksum mismatch'
    }
    $javaExe = 'java.exe'
    if ($env:JAVA_HOME) {
        $javaExe = Join-Path $env:JAVA_HOME 'bin\java.exe'
    } elseif (Test-Path -LiteralPath "$env:ProgramFiles\Android\Android Studio\jbr\bin\java.exe") {
        $javaExe = "$env:ProgramFiles\Android\Android Studio\jbr\bin\java.exe"
    }
    & $javaExe '-classpath' $wrapperJar 'org.gradle.wrapper.GradleWrapperMain' @args
    exit $LASTEXITCODE
} catch {
    Write-Error $_
    exit 1
}
