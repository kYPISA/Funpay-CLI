@echo off
chcp 65001 >nul

REM Переходим в папку, где лежит сам .bat
pushd "%~dp0"

REM Оформление окна
title FunPay CLI Bot — Kypisa Edition
color 0E

REM Запуск Python-клиента
py main.py

pause >nul
