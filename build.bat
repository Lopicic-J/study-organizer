@echo off
cd /d "%~dp0"
echo Baue Semetra.exe ...
call .venv\Scripts\activate.bat
pyinstaller Semetra.spec --clean --noconfirm
echo.
echo Fertig! Die exe liegt in: dist\Semetra\Semetra.exe
pause
