@echo off
setlocal
chcp 65001 >nul
set "PYTHONUTF8=1"
where py >nul 2>&1
if not errorlevel 1 (
  py -3 "%~dp0check_physical_android.py" --wizard %*
  goto finish
)
where python >nul 2>&1
if not errorlevel 1 (
  python "%~dp0check_physical_android.py" --wizard %*
  goto finish
)
echo Нужен Python 3. Установите Python для Windows, затем запустите этот файл ещё раз.
:finish
echo.
pause
