@echo off
setlocal EnableExtensions DisableDelayedExpansion
set "BASE=%~dp0"
set "KEY=%USERPROFILE%\.android\debug.keystore"
if not "%~1"=="" set "KEY=%~f1"
set "SDK=%ANDROID_SDK_ROOT%"
if not defined SDK set "SDK=%ANDROID_HOME%"
if not defined SDK set "SDK=%LOCALAPPDATA%\Android\Sdk"
if not "%~2"=="" set "SDK=%~f2"
set "JAVA_EXE="
if defined JAVA_HOME if exist "%JAVA_HOME%\bin\java.exe" set "JAVA_EXE=%JAVA_HOME%\bin\java.exe"
if not defined JAVA_EXE if exist "C:\Program Files\Android\Android Studio\jbr\bin\java.exe" set "JAVA_EXE=C:\Program Files\Android\Android Studio\jbr\bin\java.exe"
if not defined JAVA_EXE for /f "delims=" %%J in ('where java.exe 2^>nul') do if not defined JAVA_EXE set "JAVA_EXE=%%J"
if not defined JAVA_EXE goto no_java
for %%J in ("%JAVA_EXE%") do set "JAVA_BIN=%%~dpJ"
if not exist "%JAVA_BIN%keytool.exe" goto no_java
if not exist "%KEY%" goto no_key
set "SIGNER="
for /f "delims=" %%V in ('dir /b /ad /o-n "%SDK%\build-tools" 2^>nul') do if not defined SIGNER if exist "%SDK%\build-tools\%%V\lib\apksigner.jar" set "SIGNER=%SDK%\build-tools\%%V\lib\apksigner.jar"
if not defined SIGNER goto no_sdk
set "UNSIGNED=%BASE%DLYA_SVOIH_v0.3.134-unsigned.apk"
if not exist "%UNSIGNED%" goto missing_files
if not exist "%BASE%expected-signing-certificate.txt" goto missing_files
if not exist "%BASE%unsigned-apk-sha256.txt" goto missing_files
set /p EXPECTED_CERT=<"%BASE%expected-signing-certificate.txt"
set /p EXPECTED_APK=<"%BASE%unsigned-apk-sha256.txt"
set "CERT_FILE=%TEMP%\dlya-svoih-cert-%RANDOM%-%RANDOM%.der"
set "HASH_LOG=%TEMP%\dlya-svoih-hash-%RANDOM%-%RANDOM%.txt"
set "VERIFY_LOG=%TEMP%\dlya-svoih-verify-%RANDOM%-%RANDOM%.txt"
call :hash "%UNSIGNED%" SOURCE_HASH
if errorlevel 1 goto failed
if /i not "%SOURCE_HASH%"=="%EXPECTED_APK%" goto bad_apk
"%JAVA_BIN%keytool.exe" -exportcert -keystore "%KEY%" -storepass android -alias androiddebugkey -file "%CERT_FILE%" >nul 2>&1
if errorlevel 1 goto bad_key
call :hash "%CERT_FILE%" CERT_HASH
if errorlevel 1 goto failed
if /i not "%CERT_HASH%"=="%EXPECTED_CERT%" goto wrong_certificate
echo The original signing certificate matches. Signing locally...
"%JAVA_EXE%" -jar "%SIGNER%" sign --ks "%KEY%" --ks-key-alias androiddebugkey --ks-pass pass:android --key-pass pass:android --out "%BASE%DLYA_SVOIH_v0.3.134-signing.apk" "%UNSIGNED%"
if errorlevel 1 goto failed
"%JAVA_EXE%" -jar "%SIGNER%" verify --verbose --print-certs "%BASE%DLYA_SVOIH_v0.3.134-signing.apk" >"%VERIFY_LOG%" 2>&1
if errorlevel 1 goto failed
set "SIGNED_CERT="
for /f "tokens=2 delims=:" %%H in ('findstr /c:"Signer #1 certificate SHA-256 digest:" "%VERIFY_LOG%"') do set "SIGNED_CERT=%%H"
set "SIGNED_CERT=%SIGNED_CERT: =%"
if /i not "%SIGNED_CERT%"=="%EXPECTED_CERT%" goto wrong_certificate
move /y "%BASE%DLYA_SVOIH_v0.3.134-signing.apk" "%BASE%DLYA_SVOIH_v0.3.134.apk" >nul
if errorlevel 1 goto failed
call :cleanup
echo Created DLYA_SVOIH_v0.3.134.apk with the original certificate.
echo This is a test candidate. See README.txt for remaining Android checks.
echo The signing key stayed on this PC. Nothing was uploaded or published.
pause
exit /b 0

:hash
set "HASH_RESULT="
certutil -hashfile "%~1" SHA256 >"%HASH_LOG%" 2>&1
if errorlevel 1 exit /b 1
for /f "skip=1 delims=" %%H in ('type "%HASH_LOG%"') do if not defined HASH_RESULT set "HASH_RESULT=%%H"
set "%~2=%HASH_RESULT: =%"
exit /b 0

:no_java
echo Java and keytool were not found. Use the PC with Android Studio installed.
goto failed
:no_key
echo The original debug.keystore was not found. Do not create a new key.
echo Optional arguments: FINISH_UPDATE.cmd "path-to-original-key" "path-to-Android-SDK"
goto failed
:no_sdk
echo Android SDK Build Tools were not found. Set ANDROID_SDK_ROOT or pass the SDK as the second argument.
goto failed
:missing_files
echo Extract the entire update ZIP into one folder before running this file.
goto failed
:bad_apk
echo APK integrity check failed. Download and extract the package again.
goto failed
:bad_key
echo Cannot open the original Android debug key with the expected alias and password.
goto failed
:wrong_certificate
echo STOP: this certificate differs from the published 0.3.133 app. No update APK was accepted.
goto failed
:failed
call :cleanup
echo Signing did not complete. The existing Android application was not changed.
pause
exit /b 1
:cleanup
if defined CERT_FILE if exist "%CERT_FILE%" del /q "%CERT_FILE%" >nul 2>&1
if defined HASH_LOG if exist "%HASH_LOG%" del /q "%HASH_LOG%" >nul 2>&1
if defined VERIFY_LOG if exist "%VERIFY_LOG%" del /q "%VERIFY_LOG%" >nul 2>&1
exit /b 0
