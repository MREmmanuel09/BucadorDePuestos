@echo off
cd /d "%~dp0"
where pythonw >nul 2>nul
if not errorlevel 1 (
    start "" pythonw "%~dp0buscador\app.pyw"
    exit /b 0
)
where py >nul 2>nul
if not errorlevel 1 (
    start "" py -3w "%~dp0buscador\app.pyw"
    exit /b 0
)
echo Python no esta en el PATH. Instala Python 3 desde https://www.python.org/
echo y marca la opcion "Add python.exe to PATH" durante la instalacion.
pause
