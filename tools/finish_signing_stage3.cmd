@echo off
setlocal EnableExtensions DisableDelayedExpansion
set "BASE=%~dp0"
set "DLYA_SVOIH_NO_PAUSE=1"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%BASE%verify_signed_update.ps1" -SdkPath "%~2" -PreflightOnly
if errorlevel 1 goto failed
if exist "%BASE%DLYA_SVOIH_v0.3.134.apk" goto verify_existing
call "%BASE%sign_combined_update.cmd" "%~1" "%~2"
if errorlevel 1 goto failed
:verify_existing
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%BASE%verify_signed_update.ps1" -SdkPath "%~2"
if errorlevel 1 goto failed
echo Signature and APK payload verified. Installation over 0.3.133 is still pending.
echo Keep signed-apk-verification.json and DLYA_SVOIH_v0.3.134.apk.sha256.
echo Nothing was uploaded or published. The signing key remained on this PC.
exit /b 0
:failed
echo Signing or verification did not complete. No Android installation was performed.
exit /b 1
