@echo off
setlocal
cd /d "%~dp0"

if not exist "%ANDROID_HOME%\platforms\android-36\android.jar" if exist "%LOCALAPPDATA%\Android\Sdk\platforms\android-36\android.jar" set "ANDROID_HOME=%LOCALAPPDATA%\Android\Sdk"
if not exist "%ANDROID_HOME%\platforms\android-36\android.jar" if exist "D:\Android\Sdk\platforms\android-36\android.jar" set "ANDROID_HOME=D:\Android\Sdk"
if not exist "%ANDROID_HOME%\platforms\android-36\android.jar" if exist "D:\DAndroidSdk\Sdk\platforms\android-36\android.jar" set "ANDROID_HOME=D:\DAndroidSdk\Sdk"
set "ANDROID_SDK_ROOT="
if not exist "%ANDROID_HOME%\platforms\android-36\android.jar" (
    echo Android SDK Platform 36 not found. Install it in Android Studio SDK Manager.
    pause
    exit /b 1
)

set "SDK_FORWARD=%ANDROID_HOME:\=/%"
>"local.properties" echo sdk.dir=%SDK_FORWARD%

if not exist "%JAVA_HOME%\bin\java.exe" if exist "D:\Programs\Android Studio\jbr\bin\java.exe" set "JAVA_HOME=D:\Programs\Android Studio\jbr"
if not exist "%JAVA_HOME%\bin\java.exe" if exist "%ProgramFiles%\Android\Android Studio\jbr\bin\java.exe" set "JAVA_HOME=%ProgramFiles%\Android\Android Studio\jbr"
if not exist "%JAVA_HOME%\bin\java.exe" if exist "%LOCALAPPDATA%\Programs\Android Studio\jbr\bin\java.exe" set "JAVA_HOME=%LOCALAPPDATA%\Programs\Android Studio\jbr"
if not exist "%JAVA_HOME%\bin\java.exe" if exist "D:\Android\jdk-21\bin\java.exe" set "JAVA_HOME=D:\Android\jdk-21"
if not exist "%JAVA_HOME%\bin\java.exe" if exist "D:\Android\jdk-17\bin\java.exe" set "JAVA_HOME=D:\Android\jdk-17"
if not exist "%JAVA_HOME%\bin\java.exe" if exist "D:\AndroidBase\jdk-17\bin\java.exe" set "JAVA_HOME=D:\AndroidBase\jdk-17"
if not exist "%JAVA_HOME%\bin\java.exe" (
    echo JAVA_HOME does not point to a working JDK 17 or newer.
    pause
    exit /b 1
)

if not exist "gradle\wrapper\gradle-wrapper.jar" (
    echo Gradle wrapper JAR not found in this project folder.
    pause
    exit /b 1
)

"%JAVA_HOME%\bin\java.exe" -classpath "gradle\wrapper\gradle-wrapper.jar" org.gradle.wrapper.GradleWrapperMain :app:assembleDebug
if errorlevel 1 (
    echo.
    echo APK BUILD FAILED
    pause
    exit /b 1
)

if not exist "app\build\outputs\apk\debug\app-debug.apk" (
    echo APK BUILD FINISHED WITHOUT AN APK. Check the Gradle output above.
    pause
    exit /b 1
)

copy /Y "app\build\outputs\apk\debug\app-debug.apk" "DLYA_SVOIH_v0.3.121-debug.apk" >nul
if errorlevel 1 (
    echo APK COPY FAILED
    pause
    exit /b 1
)

echo.
echo APK READY:
echo %CD%\DLYA_SVOIH_v0.3.121-debug.apk
pause

