@echo off
chcp 65001 >nul

title FunPay CLI Bot - Notifier
color 0E

REM Переходим в папку Notifer
cd /d "%~dp0"

cls
echo =======================================
echo      FunPay CLI Bot - Notifier
echo =======================================
echo.

py main.py

echo.
echo Press any key to exit...
pause >nul
