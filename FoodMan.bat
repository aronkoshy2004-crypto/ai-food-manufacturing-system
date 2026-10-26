@echo off
setlocal
cd /d "%~dp0"

:: Food Man Desktop Launcher (Hidden Window)
:: Starts Waitress WSGI server if not running,
:: Starts Cloudflare tunnel and writes .public_url,
:: Waits until /health responds, then opens Edge or Chrome in app mode.

where pythonw >nul 2>&1
if %ERRORLEVEL% equ 0 (
    start "" pythonw "%~dp0scripts\launcher.py"
) else (
    start "" powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -Command "& python '%~dp0scripts\launcher.py'"
)

exit /b 0
