@echo off
setlocal
cd /d "%~dp0"

echo ============================================
echo  PATTI REEL - rebuild and publish
echo ============================================
echo.

where python >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Python not found on PATH.
  pause
  exit /b 1
)

python publish.py %*
if errorlevel 1 (
  echo.
  echo [ERROR] Failed. See the message above.
  pause
  exit /b 1
)

echo.
pause
endlocal
