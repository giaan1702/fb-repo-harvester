@echo off
title Autonomous Knowledge Vault UI
cd /d "%~dp0"
echo Dang khoi dong giao dien Knowledge Vault Dashboard...
python -m uvicorn vault_engine.server:app --host 127.0.0.1 --port 7860 --reload
pause
