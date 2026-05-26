@echo off
echo ========================================
echo   UVM Generator - Full Stack
echo ========================================
echo.

cd /d "%~dp0.."

echo [1/2] Installing backend dependencies...
pip install fastapi uvicorn pydantic python-multipart websockets -q 2>nul

echo.
echo [2/2] Installing frontend dependencies...
cd frontend
if not exist node_modules (
    npm install
)

echo.
echo ========================================
echo   Starting Servers...
echo ========================================
echo.
echo Backend:  http://localhost:8000
echo API Docs: http://localhost:8000/docs
echo Frontend: http://localhost:5173
echo.

cd ..
start "UVM Backend" cmd /c "python -m uvicorn backend.main:app --reload --port 8000"

timeout /t 3 /nobreak >nul

cd frontend
start "UVM Frontend" cmd /c "npm run dev"

echo.
echo Both servers starting in background...
echo Press any key to exit this window (servers keep running)
pause >nul
