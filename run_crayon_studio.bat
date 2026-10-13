@echo off
title CrayonStudio Desktop
cd /d "%~dp0"
echo Starting CrayonStudio Desktop App...
"C:\Users\gagee\AppData\Local\Programs\Python\Python314\python.exe" app.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo CrayonStudio exited with error code %ERRORLEVEL%.
    pause
)
