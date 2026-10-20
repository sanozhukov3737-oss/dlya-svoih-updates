#!/bin/sh
# Lightweight launcher. First run fetches the official, checksum-pinned wrapper JAR.
set -eu
APP_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
WRAPPER_JAR="$APP_ROOT/gradle/wrapper/gradle-wrapper.jar"
EXPECTED_JAR_SHA=81a82aaea5abcc8ff68b3dfcb58b3c3c429378efd98e7433460610fecd7ae45f
checksum() {
    if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | cut -d ' ' -f 1
    else shasum -a 256 "$1" | cut -d ' ' -f 1; fi
}
if [ ! -f "$WRAPPER_JAR" ]; then
    WRAPPER_TEMP=$(mktemp "$APP_ROOT/gradle/wrapper/wrapper.XXXXXX")
    trap 'rm -f "$WRAPPER_TEMP"' EXIT HUP INT TERM
    curl --fail --location --connect-timeout 15 --max-time 120 \
        https://raw.githubusercontent.com/gradle/gradle/v8.13.0/gradle/wrapper/gradle-wrapper.jar -o "$WRAPPER_TEMP"
    [ "$(checksum "$WRAPPER_TEMP")" = "$EXPECTED_JAR_SHA" ] || { echo 'Gradle wrapper checksum mismatch' >&2; exit 1; }
    mv "$WRAPPER_TEMP" "$WRAPPER_JAR"
    trap - EXIT HUP INT TERM
fi
[ "$(checksum "$WRAPPER_JAR")" = "$EXPECTED_JAR_SHA" ] || { echo 'Gradle wrapper checksum mismatch' >&2; exit 1; }
if [ -n "${JAVA_HOME:-}" ]; then JAVA_COMMAND="$JAVA_HOME/bin/java"; else JAVA_COMMAND=java; fi
exec "$JAVA_COMMAND" -classpath "$WRAPPER_JAR" org.gradle.wrapper.GradleWrapperMain "$@"
