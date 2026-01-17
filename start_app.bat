@echo off
cd /d "%~dp0"
echo Starting Update Checker Web Platform...
echo Starting Backend Server...
start /min "Update Checker Backend" cmd /k "python -m uvicorn web-platform.backend.app:app --host 127.0.0.1 --port 8000 --reload"

echo Waiting for server to initialize (3 seconds)...
timeout /t 3 /nobreak >nul

echo Opening Web Interface...
start http://127.0.0.1:8000

echo.
echo ========================================================
echo  Update Checker Started Successfully!
echo  - Backend is running in a minimized window.
echo  - Frontend is opened in your default browser.
echo  - To stop the app, close the backend window.
echo ========================================================
echo.
pause
