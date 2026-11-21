@echo off
rem Releve les prix du jour puis met a jour rapport.html
cd /d "%~dp0"
python -X utf8 prixjuste.py tout >> journal.txt 2>&1
