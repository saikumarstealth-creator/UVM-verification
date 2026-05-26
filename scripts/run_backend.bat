@echo off
echo ========================================
echo   UVM Generator - Backend
echo ========================================
echo.

cd /d "%~dp0.."

echo Installing backend dependencies...
pip install fastapi uvicorn pydantic python-multipart websockets -q

echo.
echo Starting FastAPI backend on http://localhost:8000
echo.
echo API Docs: http://localhost:8000/docs
echo.

python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
