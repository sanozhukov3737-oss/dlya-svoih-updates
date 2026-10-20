@echo off
setlocal
set "WRAPPER_JAR=%~dp0gradle\wrapper\gradle-wrapper.jar"
if not exist "%WRAPPER_JAR%" (
    echo Gradle wrapper JAR not found: %WRAPPER_JAR%
    exit /b 1
)
set "JAVA_EXE=java.exe"
if defined JAVA_HOME set "JAVA_EXE=%JAVA_HOME%\bin\java.exe"
"%JAVA_EXE%" -classpath "%WRAPPER_JAR%" org.gradle.wrapper.GradleWrapperMain %*
exit /b %errorlevel%
