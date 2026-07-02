@echo off
title OMRON LD Robot Control
color 0A

REM Projektpfad relativ zum Batch-Skript-Ordner (eine Ebene höher)
for %%I in ("%~dp0..") do set "PROJECT_PATH=%%~fI"

REM Prüfen ob Projektordner existiert
if not exist "%PROJECT_PATH%\main.py" (
    echo ❌ main.py nicht gefunden!
    echo Pfad: %PROJECT_PATH%\main.py
    timeout /t 3 >nul
    exit /b 1
)

REM Direkt zum Projektverzeichnis wechseln
cd /d "%PROJECT_PATH%"

REM Python prüfen (still/schweigend)
where python >nul 2>&1
if %errorlevel% neq 0 (
    msg * "❌ Python nicht gefunden! Bitte Python 3.8+ installieren."
    exit /b 1
)

REM 🚀 DIREKT NORMALEN MODUS STARTEN (KEINE MENÜS!)
echo Starte OMRON Robot Control...
python main.py

REM Nur bei Fehler warten
if %errorlevel% neq 0 timeout /t 5 >nul
