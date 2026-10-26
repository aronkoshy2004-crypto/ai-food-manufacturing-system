@echo off
setlocal
cd /d "%~dp0"

:: Food Man Stop Launcher
:: Stops Waitress server, Cloudflare tunnel, and cleans up .public_url.

python "%~dp0scripts\stop_foodman.py"

echo.
echo [Food Man] All background processes stopped.
timeout /t 2 >nul
exit /b 0
