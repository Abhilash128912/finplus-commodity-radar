"""
FinPlus+ MCX Commodity Radar - FastAPI REST API & Server Layer
Port: 8002
"""

import os
import sys

# Ensure D:\AI_APPS is in sys.path so finplus_core can be imported seamlessly
_RADAR_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_AI_APPS_ROOT = os.path.dirname(_RADAR_DIR)
if _AI_APPS_ROOT not in sys.path:
    sys.path.insert(0, _AI_APPS_ROOT)
if _RADAR_DIR not in sys.path:
    sys.path.insert(0, _RADAR_DIR)

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from typing import Dict, Any

from config.settings import APP_NAME, APP_CODE, SERVER_PORT, NTFY_TOPIC
from src.scheduler.commodity_scheduler import CommodityScheduler
from src.analytics.session_clock import MCXSessionClock
from src.analytics.eia_calendar_shield import EIACalendarShield
from src.utils.time_and_logger import setup_logger, get_utc_iso, get_ist_now

logger = setup_logger("CommodityServer")

# Global scheduler instance
scheduler = CommodityScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {APP_NAME} ({APP_CODE}) on port {SERVER_PORT}...")
    # Start scheduler daemon
    scheduler.start_background_loop(interval_seconds=60)
    yield
    logger.info("Shutting down Commodity Radar...")
    scheduler.stop()

app = FastAPI(title=APP_NAME, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
os.makedirs(FRONTEND_DIR, exist_ok=True)

# Mount static folder
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

@app.get("/")
def serve_dashboard():
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return JSONResponse({"status": "ready", "message": "Frontend index.html initializing..."})

@app.get("/floater")
def serve_floater():
    floater_path = os.path.join(FRONTEND_DIR, "floater.html")
    if os.path.exists(floater_path):
        return FileResponse(floater_path)
    return JSONResponse({"status": "ready", "message": "Frontend floater.html initializing..."})

@app.get("/api/status")
def get_system_status() -> Dict[str, Any]:
    session = MCXSessionClock.get_session_info()
    return {
        "app_name": APP_NAME,
        "app_code": APP_CODE,
        "port": SERVER_PORT,
        "status": "ONLINE",
        "exchange_session": session["phase_label"],
        "exchange_open": session["is_open"],
        "gateway_status": "GATEWAY: ONLINE (INDSTOCKS MCX AUTHENTICATED)",
        "utc_time": get_utc_iso(),
        "ist_time": get_ist_now().strftime("%I:%M:%S %p IST"),
        "ntfy_topic": f"https://ntfy.sh/{NTFY_TOPIC}"
    }

@app.get("/api/scan")
def get_latest_scan(force: bool = False) -> Dict[str, Any]:
    if force or not scheduler.latest_scan_results:
        return scheduler.run_full_scan()
    return scheduler.latest_scan_results

@app.get("/api/eia-shield")
def get_eia_shield_status() -> Dict[str, Any]:
    crude = EIACalendarShield.get_shield_status("CRUDEOILM")
    natgas = EIACalendarShield.get_shield_status("NATGASMINI")
    return {
        "crude_oil": crude,
        "natural_gas": natgas,
        "timestamp_utc": get_utc_iso()
    }

@app.post("/api/trigger-pulse")
def trigger_pulse() -> Dict[str, Any]:
    """Forces an instant scan and dispatches test alert to NTFY."""
    logger.info("Manual test pulse requested via API")
    scan = scheduler.run_full_scan()
    # Trigger one forced alert for the highest scoring commodity
    best_sym = None
    best_score = -1
    for sym, data in scan.get("commodities", {}).items():
        if data.get("confluence_score", 0) > best_score:
            best_score = data.get("confluence_score", 0)
            best_sym = sym
            
    if best_sym:
        scheduler.ntfy.send_breakout_alert(scan["commodities"][best_sym], force=True)
        
    return {
        "status": "SUCCESS",
        "message": f"Scan triggered. Evaluated {len(scan.get('commodities', {}))} assets.",
        "top_asset": best_sym,
        "score": best_score
    }

