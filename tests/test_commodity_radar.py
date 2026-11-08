"""
FinPlus+ MCX Commodity Radar - Automated Test Suite
Verifies quantitative engine, session clock, EIA shield, and REST API.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timezone
import zoneinfo
from fastapi.testclient import TestClient

from config.settings import COMMODITY_SPECS
from src.analytics.session_clock import MCXSessionClock
from src.analytics.eia_calendar_shield import EIACalendarShield
from src.analytics.commodity_luxalgo_engine import CommodityLuxAlgoEngine
from src.analytics.commodity_priority_engine import CommodityPriorityEngine
from src.api.server import app

client = TestClient(app)
IST = zoneinfo.ZoneInfo("Asia/Kolkata")

def test_session_clock_phases():
    """Verifies MCX session clock accurately classifies market hours."""
    # 1. Weekend
    dt_weekend = datetime(2026, 11, 8, 14, 0, tzinfo=IST) # Sunday
    res_weekend = MCXSessionClock.get_session_info(dt_weekend)
    assert res_weekend["is_open"] is False
    assert "WEEKEND" in res_weekend["phase_label"]
    
    # 2. Weekday Overnight
    dt_night = datetime(2026, 11, 9, 3, 0, tzinfo=IST) # Monday 3 AM
    res_night = MCXSessionClock.get_session_info(dt_night)
    assert res_night["is_open"] is False
    assert "OVERNIGHT" in res_night["phase_label"]
    
    # 3. Weekday US Prime Session (19:00 IST)
    dt_prime = datetime(2026, 11, 9, 19, 0, tzinfo=IST) # Monday 7 PM
    res_prime = MCXSessionClock.get_session_info(dt_prime)
    assert res_prime["is_open"] is True
    assert res_prime["phase"] == "US_SESSION_PRIME"
    assert res_prime["trade_permission"] is True
    
    # 4. Mandatory Square-off (23:20 IST)
    dt_sqoff = datetime(2026, 11, 9, 23, 20, tzinfo=IST)
    res_sqoff = MCXSessionClock.get_session_info(dt_sqoff)
    assert res_sqoff["phase"] == "INTRADAY_SQUARE_OFF"
    assert res_sqoff["trade_permission"] is False

def test_eia_calendar_shield():
    """Verifies EIA shield triggers on Wednesday (Crude) and Thursday (NatGas) at 8:00 PM IST."""
    # Wednesday 19:58 IST (2 mins before Crude report)
    dt_wed_shield = datetime(2026, 11, 11, 19, 58, tzinfo=IST)
    crude_shield = EIACalendarShield.get_shield_status("CRUDEOILM", dt_wed_shield)
    assert crude_shield["shield_active"] is True
    assert "SHIELD ACTIVE" in crude_shield["message"]
    
    # NatGas on Wednesday should be clear
    natgas_wed = EIACalendarShield.get_shield_status("NATGASMINI", dt_wed_shield)
    assert natgas_wed["shield_active"] is False
    
    # Thursday 20:00 IST (Natgas release)
    dt_thu_shield = datetime(2026, 11, 12, 20, 0, tzinfo=IST)
    natgas_shield = EIACalendarShield.get_shield_status("NATGASMINI", dt_thu_shield)
    assert natgas_shield["shield_active"] is True
    
    # Gold Petal is exempt from EIA storage reports
    gold_shield = EIACalendarShield.get_shield_status("GOLDPETAL", dt_wed_shield)
    assert gold_shield["shield_active"] is False

def test_commodity_luxalgo_engine():
    """Verifies LuxAlgo compression, trend gating, and risk/gain rupee calculations."""
    engine = CommodityLuxAlgoEngine()
    
    # Generate synthetic 60-bar 15m dataframe
    n = 60
    base_price = 8000.0 # ~Crude Oil in INR
    closes = np.full(n, base_price)
    # create small range compression
    for i in range(20):
        closes[-(i+1)] = base_price + (i % 3) * 5.0
    
    # last bar creates strong breakout above box
    closes[-1] = base_price + 80.0
    
    df = pd.DataFrame({
        'Open': closes - 2.0,
        'High': closes + 5.0,
        'Low': closes - 5.0,
        'Close': closes,
        'Volume': np.full(n, 1000)
    })
    df['Volume'].iloc[-1] = 2000 # volume expansion
    
    res = engine.analyze_commodity("CRUDEOILM", df)
    assert res["symbol"] == "CRUDEOILM"
    assert res["ltp"] > 0
    assert res["box_top"] > 0
    assert res["box_bottom"] > 0
    assert 0 <= res["confluence_score"] <= 100
    assert res["rupee_multiplier"] == 10.0 # 10 Barrels
    assert "score_breakdown" in res

def test_commodity_priority_and_options():
    """Verifies #1 priority ranking and option strike directives."""
    # 1. Crude Oil ATM strike step 50
    strike_crude = CommodityPriorityEngine.calculate_atm_strike(8528.0, 50)
    assert strike_crude == 8550
    
    # 2. Natgas ATM strike step 5
    strike_natgas = CommodityPriorityEngine.calculate_atm_strike(281.4, 5)
    assert strike_natgas == 280
    
    # 3. Test Option Directive for Bullish Breakout
    mock_bull_analysis = {
        "symbol": "CRUDEOILM",
        "ltp": 8528.0,
        "directive": "BUY LONG (BREAKOUT)",
        "box_top": 8490.0,
        "box_bottom": 8410.0,
        "eia_info": {"shield_active": False},
        "session_info": {"is_open": True}
    }
    opt_bull = CommodityPriorityEngine.determine_option_directive("CRUDEOILM", mock_bull_analysis)
    assert opt_bull["type"] == "CALL"
    assert "8550 CE" in opt_bull["contract"]
    assert "BUY" in opt_bull["recommended_action"]
    
    # 4. Test Option Directive for Bearish Breakdown
    mock_bear_analysis = {
        "symbol": "NATGASMINI",
        "ltp": 281.0,
        "directive": "SELL SHORT (BREAKDOWN)",
        "box_top": 285.0,
        "box_bottom": 283.0,
        "eia_info": {"shield_active": False},
        "session_info": {"is_open": True}
    }
    opt_bear = CommodityPriorityEngine.determine_option_directive("NATGASMINI", mock_bear_analysis)
    assert opt_bear["type"] == "PUT"
    assert "280 PE" in opt_bear["contract"]
    
    # 5. Test Priority Selection
    mock_pool = {
        "CRUDEOILM": {
            "display_name": "Crude Oil Mini",
            "confluence_score": 85,
            "directive": "BUY LONG (BREAKOUT)",
            "ltp": 8528.0,
            "box_width_pct": 1.2,
            "eia_info": {"shield_active": False}
        },
        "NATGASMINI": {
            "display_name": "Natural Gas Mini",
            "confluence_score": 60,
            "directive": "HOLD CASH / STANDBY",
            "ltp": 281.0,
            "box_width_pct": 2.5,
            "eia_info": {"shield_active": False}
        },
        "GOLDPETAL": {
            "display_name": "Gold Petal",
            "confluence_score": 50,
            "directive": "HOLD CASH / STANDBY",
            "ltp": 8000.0,
            "box_width_pct": 3.0,
            "eia_info": {"shield_active": False}
        }
    }
    p_res = CommodityPriorityEngine.select_priority_commodity(mock_pool)
    assert p_res["symbol"] == "CRUDEOILM"
    assert "CRUDEOIL 8550 CE" in p_res["option_directive"]["contract"]

def test_api_endpoints():
    """Verifies FastAPI REST endpoints."""
    # /api/status
    res = client.get("/api/status")
    assert res.status_code == 200
    data = res.json()
    assert data["app_code"] == "APP-03"
    assert data["port"] == 8002
    assert "exchange_session" in data
    
    # /api/eia-shield
    res_eia = client.get("/api/eia-shield")
    assert res_eia.status_code == 200
    eia_data = res_eia.json()
    assert "crude_oil" in eia_data
    assert "natural_gas" in eia_data

if __name__ == "__main__":
    pytest.main(["-v", __file__])

