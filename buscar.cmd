@echo off
cd /d "%~dp0"
where python >nul 2>nul
if not errorlevel 1 goto :py
where py >nul 2>nul
if not errorlevel 1 goto :py3
echo Python no esta en el PATH. Instala Python 3 desde https://www.python.org/
echo y marca la opcion "Add python.exe to PATH" durante la instalacion.
pause
exit /b 1
:py
python buscador\main.py
exit /b %errorlevel%
:py3
py -3 buscador\main.py
exit /b %errorlevel%
