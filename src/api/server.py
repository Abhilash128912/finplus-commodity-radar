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
import time
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from typing import Dict, Any, Optional

from config.settings import APP_NAME, APP_CODE, SERVER_PORT, NTFY_TOPIC
from src.scheduler.commodity_scheduler import CommodityScheduler
from src.analytics.session_clock import MCXSessionClock
from src.analytics.eia_calendar_shield import EIACalendarShield
from src.utils.time_and_logger import setup_logger, get_utc_iso, get_ist_now

logger = setup_logger("CommodityServer")

# Lazy/safe global scheduler instance (avoid import-time crash when INDMONEY_* env vars are absent)
scheduler: Optional[CommodityScheduler] = None
_scheduler_init_error: Optional[str] = None


def get_scheduler() -> Optional[CommodityScheduler]:
    global scheduler, _scheduler_init_error
    if scheduler is not None:
        return scheduler
    try:
        scheduler = CommodityScheduler()
        _scheduler_init_error = None
    except Exception as e:
        _scheduler_init_error = str(e)
        logger.warning(f"CommodityScheduler initialization unavailable: {e}")
    return scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {APP_NAME} ({APP_CODE}) on port {SERVER_PORT}...")
    sched = get_scheduler()
    if sched is not None:
        sched.start_background_loop(interval_seconds=60)
    else:
        logger.warning(f"Background scheduler not started: {_scheduler_init_error}")
    yield
    logger.info("Shutting down Commodity Radar...")
    if scheduler is not None:
        scheduler.stop()

app = FastAPI(title=APP_NAME, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
os.makedirs(FRONTEND_DIR, exist_ok=True)

# Mount static folder
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

@app.api_route("/", methods=["GET", "HEAD"])
def serve_dashboard():
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return JSONResponse({"status": "ready", "message": "Frontend index.html initializing..."})

@app.api_route("/health", methods=["GET", "HEAD"])
def health_check():
    return {"status": "ok", "app": APP_NAME}

@app.get("/floater")
def serve_floater():
    floater_path = os.path.join(FRONTEND_DIR, "floater.html")
    if os.path.exists(floater_path):
        return FileResponse(floater_path)
    return JSONResponse({"status": "ready", "message": "Frontend floater.html initializing..."})

@app.get("/api/status")
def get_system_status() -> Dict[str, Any]:
    session = MCXSessionClock.get_session_info()
    sched = get_scheduler()
    if sched is None:
        gateway_status = f"GATEWAY: DEGRADED ({_scheduler_init_error or 'SCHEDULER UNAVAILABLE'})"
    else:
        auth_client = getattr(getattr(sched, "ind_feed", None), "auth_client", None)
        cooldown_until = getattr(getattr(sched, "ind_feed", None), "_broker_cooldown_until", 0.0)
        if auth_client is None:
            gateway_status = "GATEWAY: DEGRADED (AUTH CLIENT UNAVAILABLE)"
        elif time.time() < cooldown_until:
            gateway_status = "GATEWAY: COOLDOWN (INDSTOCKS RATE/AUTH BACKOFF)"
        elif auth_client.is_token_valid():
            gateway_status = "GATEWAY: ONLINE (INDSTOCKS MCX AUTHENTICATED)"
        elif auth_client.access_token:
            gateway_status = "GATEWAY: TOKEN EXPIRED (REFRESH REQUIRED)"
        else:
            gateway_status = "GATEWAY: UNAUTHENTICATED (NO ACTIVE TOKEN)"

    return {
        "app_name": APP_NAME,
        "app_code": APP_CODE,
        "port": SERVER_PORT,
        "status": "ONLINE",
        "exchange_session": session["phase_label"],
        "exchange_open": session["is_open"],
        "gateway_status": gateway_status,
        "utc_time": get_utc_iso(),
        "ist_time": get_ist_now().strftime("%I:%M:%S %p IST"),
        "ntfy_topic": f"https://ntfy.sh/{NTFY_TOPIC}"
    }

@app.get("/api/scan")
def get_latest_scan(force: bool = False) -> Dict[str, Any]:
    sched = get_scheduler()
    if sched is None:
        raise HTTPException(status_code=503, detail=f"Scheduler unavailable: {_scheduler_init_error}")
    if force:
        return sched.run_full_scan()
    latest = sched.get_latest_scan_results()
    if not latest:
        return sched.run_full_scan()
    return latest

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
    sched = get_scheduler()
    if sched is None:
        raise HTTPException(status_code=503, detail=f"Scheduler unavailable: {_scheduler_init_error}")
    logger.info("Manual test pulse requested via API")
    scan = sched.run_full_scan()
    # Trigger one forced alert for the highest scoring commodity
    best_sym = None
    best_score = -1
    for sym, data in scan.get("commodities", {}).items():
        if data.get("confluence_score", 0) > best_score:
            best_score = data.get("confluence_score", 0)
            best_sym = sym
            
    if best_sym:
        sched.ntfy.send_breakout_alert(scan["commodities"][best_sym], force=True)
        
    return {
        "status": "SUCCESS",
        "message": f"Scan triggered. Evaluated {len(scan.get('commodities', {}))} assets.",
        "top_asset": best_sym,
        "score": best_score
    }

