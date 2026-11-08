"""
FinPlus+ Commodity Radar - Configuration & Contract Registry
"""

from typing import Dict, Any

APP_NAME = "FinPlus+ MCX Commodity Radar"
APP_CODE = "APP-03"
SERVER_PORT = 8002
SERVER_HOST = "127.0.0.1"

# NTFY Configuration
NTFY_TOPIC = "Finplus-Commodity"
NTFY_SERVER = "https://ntfy.sh"

# MCX Trading Session Hours (IST)
MCX_MARKET_OPEN_IST = "09:00"
MCX_MARKET_CLOSE_IST = "23:30"
PRE_US_COMPRESSION_START_IST = "14:00"
PRE_US_COMPRESSION_END_IST = "17:30"
US_SESSION_PRIME_START_IST = "18:00"
US_SESSION_PRIME_END_IST = "21:30"
INTRADAY_SQUARE_OFF_IST = "23:20"

# Contract Registry & Micro/Mini Specifications
COMMODITY_SPECS: Dict[str, Dict[str, Any]] = {
    "CRUDEOILM": {
        "display_name": "Crude Oil Mini",
        "symbol": "CRUDEOILM",
        "benchmark_ticker": "CL=F",
        "lot_unit": "10 Barrels",
        "lot_size": 10,
        "tick_size": 1.0,
        "rupee_multiplier_per_point": 10.0,
        "typical_margin_inr": 22000,
        "eia_day": 2, # Wednesday (0=Monday, 2=Wednesday)
        "eia_time_ist": "20:00",
        "description": "WTI Light Sweet Crude Oil Mini (MCX). High trend momentum during US evening session."
    },
    "NATGASMINI": {
        "display_name": "Natural Gas Mini",
        "symbol": "NATGASMINI",
        "benchmark_ticker": "NG=F",
        "lot_unit": "250 mmBtu",
        "lot_size": 250,
        "tick_size": 0.10,
        "rupee_multiplier_per_point": 250.0,
        "typical_margin_inr": 28000,
        "eia_day": 3, # Thursday (3=Thursday)
        "eia_time_ist": "20:00",
        "description": "Henry Hub Natural Gas Mini (MCX). High volatility with explosive expansion breakouts."
    },
    "GOLDPETAL": {
        "display_name": "Gold Petal",
        "symbol": "GOLDPETAL",
        "benchmark_ticker": "GC=F",
        "lot_unit": "1 Gram",
        "lot_size": 1,
        "tick_size": 1.0,
        "rupee_multiplier_per_point": 1.0,
        "typical_margin_inr": 1000,
        "eia_day": None,
        "eia_time_ist": None,
        "description": "999 Purity Gold Petal (MCX). Ultra-micro contract for precise risk budgeting and multi-lot scaling."
    }
}

# Quantitative Algorithm Parameters
LUXALGO_LOOKBACK = 15
LUXALGO_ATR_PERIOD = 200
LUXALGO_ATR_MULT = 0.85
EMA_FAST_PERIOD = 20
EMA_TREND_PERIOD = 50
VOLUME_EXPANSION_THRESHOLD = 1.2 # 120% of 20-period average volume
RISK_REWARD_RATIO = 1.5
MAX_STOP_LOSS_PCT = 0.015 # Cap risk at 1.5% maximum

