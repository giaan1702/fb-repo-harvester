@echo off
title FB Repo Harvester UI
cd /d "%~dp0"
echo Dang khoi dong giao dien FB Repo Harvester Web UI...
python -m fb_harvester.server
pause
