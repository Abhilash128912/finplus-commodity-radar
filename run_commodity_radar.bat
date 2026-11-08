@echo off
title FinPlus+ MCX Commodity Radar (Port 8002)
echo =========================================================================
echo    FINPLUS+ MCX COMMODITY RADAR (APP-03)
echo    Natural Gas Mini - Crude Oil Mini - Gold Petal
echo    Port: 8002 | Push: ntfy.sh/Finplus-Commodity
echo =========================================================================
echo.
cd /d D:\AI_APPS\finplus_commodity_radar
python -m uvicorn src.api.server:app --host 127.0.0.1 --port 8002
pause

