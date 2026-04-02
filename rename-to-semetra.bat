@echo off
REM ============================================================
REM  Semetra — Ordner umbenennen von study-organizer zu semetra
REM  Einfach doppelklicken, NACHDEM du das Ordner-Fenster
REM  geschlossen hast (sonst ist er gesperrt).
REM ============================================================

echo Verschiebe Ordner...

REM Gehe einen Ordner nach oben
cd /d "%~dp0.."

REM Prüfen ob der Ordner noch study-organizer heisst
if exist "study-organizer" (
    rename "study-organizer" "semetra"
    echo.
    echo Fertig! Der Ordner heisst jetzt: semetra
    echo Bitte oeffne in Zukunft: semetra\
) else (
    echo Der Ordner 'study-organizer' wurde nicht gefunden.
    echo Vielleicht wurde er schon umbenannt?
)

echo.
pause
