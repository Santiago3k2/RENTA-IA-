@echo off
title RENTA IA
cd /d "%~dp0web"
start "" http://localhost:8765
python app.py
