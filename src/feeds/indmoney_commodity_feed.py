"""
FinPlus+ INDstocks MCX Commodity Feed
Direct, official broker integration with INDstocks API (https://api.indstocks.com).
Fetches live MCX quotes, Open Interest, Day High/Low, and Options chains for:
  - Crude Oil Mini (CRUDEOILM)
  - Natural Gas Mini (NATGASMINI)
  - Gold Petal (GOLDPETAL)
"""

import os
import sys

# Ensure D:\AI_APPS is in sys.path
_RADAR_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_AI_APPS_ROOT = os.path.dirname(_RADAR_DIR)
if _AI_APPS_ROOT not in sys.path:
    sys.path.insert(0, _AI_APPS_ROOT)

import time
import json
import pandas as pd
import requests
from typing import Dict, Any, List, Optional
from datetime import datetime

# Import INDstocks authentication client from finplus_core
from finplus_core.auth import INDMoneyAuthClient
from src.utils.time_and_logger import setup_logger

logger = setup_logger("INDMoneyCommodityFeed")

# Verified Active MCX Contract Security IDs on INDstocks
ACTIVE_MCX_CONTRACTS = {
    "CRUDEOILM": {
        "security_id": "573423",
        "scrip_code": "MCX_573423",
        "trading_symbol": "CRUDEOILM 19 Nov Fut",
        "lot_size": 10,
        "tick_size": 1.0,
        "rupee_multiplier": 10.0,
        "strike_step": 50,
        "display_name": "Crude Oil Mini"
    },
    "NATGASMINI": {
        "security_id": "574320",
        "scrip_code": "MCX_574320",
        "trading_symbol": "NATGASMINI 24 Nov Fut",
        "lot_size": 250,
        "tick_size": 0.10,
        "rupee_multiplier": 250.0,
        "strike_step": 5,
        "display_name": "Natural Gas Mini"
    },
    "GOLDPETAL": {
        "security_id": "574841",
        "scrip_code": "MCX_574841",
        "trading_symbol": "GOLDPETAL 30 Nov Fut",
        "lot_size": 1,
        "tick_size": 1.0,
        "rupee_multiplier": 1.0,
        "strike_step": 500,
        "display_name": "Gold Petal"
    }
}

class INDMoneyCommodityFeed:
    BASE_URL = "https://api.indstocks.com"
    QUOTES_ENDPOINT = "/market/quotes/full"
    INSTRUMENTS_ENDPOINT = "/market/instruments?source=mcx"

    def __init__(self, cache_ttl_seconds: int = 15):
        self.cache_ttl = cache_ttl_seconds
        self.auth_client = INDMoneyAuthClient()
        self._quote_cache: Dict[str, Any] = {}
        self._cache_time: float = 0.0
        self._instruments_df: Optional[pd.DataFrame] = None
        
        # Load local instruments dump if available
        dump_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "mcx_instruments_sample.txt")
        if os.path.exists(dump_path):
            try:
                self._instruments_df = pd.read_csv(dump_path, low_memory=False)
                logger.info(f"Loaded {len(self._instruments_df)} MCX instruments from local INDstocks registry.")
            except Exception as e:
                logger.warning(f"Could not load local instruments dump: {e}")

    def _get_valid_headers(self) -> Dict[str, str]:
        """Gets valid authorization headers, refreshing token with TOTP if needed."""
        try:
            return self.auth_client.get_auth_headers()
        except Exception:
            logger.info("Generating fresh INDstocks token via TOTP...")
            self.auth_client.generate_fresh_token()
            return self.auth_client.get_auth_headers()

    def fetch_live_quotes(self, force: bool = False) -> Dict[str, Any]:
        """
        Fetches real-time quotes directly from INDstocks API for all active MCX contracts.
        """
        now = time.time()
        if not force and self._quote_cache and (now - self._cache_time) < self.cache_ttl:
            return self._quote_cache

        headers = self._get_valid_headers()
        formatted = {}

        for symbol, meta in ACTIVE_MCX_CONTRACTS.items():
            scrip = meta["scrip_code"]
            url = f"{self.BASE_URL}{self.QUOTES_ENDPOINT}?scrip-codes={scrip}"
            
            try:
                resp = requests.get(url, headers=headers, timeout=5)
                if resp.status_code in (401, 403):
                    logger.warning(f"INDstocks token rejected (HTTP {resp.status_code}). Refreshing token via TOTP...")
                    self.auth_client.generate_fresh_token()
                    headers = self.auth_client.get_auth_headers()
                    resp = requests.get(url, headers=headers, timeout=5)

                if resp.status_code == 200:
                    payload = resp.json()
                    q = payload.get("data", {}).get(scrip, {})
                    
                    ltp = float(q.get("live_price", 0.0))
                    high = float(q.get("day_high", ltp))
                    low = float(q.get("day_low", ltp))
                    open_p = float(q.get("day_open", ltp))
                    prev_c = float(q.get("prev_close", ltp))
                    chg_pct = float(q.get("day_change_percentage", 0.0))
                    oi = int(q.get("open_interest", 0))
                    vol = int(q.get("volume", 0))
                    
                    formatted[symbol] = {
                        "symbol": symbol,
                        "display_name": meta["display_name"],
                        "trading_symbol": meta["trading_symbol"],
                        "security_id": meta["security_id"],
                        "scrip_code": scrip,
                        "ltp": ltp,
                        "high": high,
                        "low": low,
                        "open": open_p,
                        "prev_close": prev_c,
                        "change_pct": chg_pct,
                        "open_interest": oi,
                        "volume": vol,
                        "lot_size": meta["lot_size"],
                        "rupee_multiplier": meta["rupee_multiplier"],
                        "source": "INDstocks MCX API"
                    }
                else:
                    logger.warning(f"INDstocks quote error for {scrip}: HTTP {resp.status_code}")
            except Exception as e:
                logger.error(f"Error fetching quote for {scrip}: {e}")

        if formatted:
            self._quote_cache = formatted
            self._cache_time = now
            logger.info(f"Updated live MCX quotes from INDstocks: Crude ₹{formatted.get('CRUDEOILM', {}).get('ltp', 0):,.0f}, NatGas ₹{formatted.get('NATGASMINI', {}).get('ltp', 0):,.1f}, Gold ₹{formatted.get('GOLDPETAL', {}).get('ltp', 0):,.0f}")

        return self._quote_cache

    def find_atm_option_contract(self, symbol: str, option_type: str, atm_strike: int) -> Optional[Dict[str, Any]]:
        """
        Searches the INDstocks MCX instrument master for the exact matching ATM Option contract.
        Returns trading symbol and security ID.
        """
        if self._instruments_df is None or self._instruments_df.empty:
            return None

        # Clean symbol matching (e.g. CRUDEOILM or NATGASMINI)
        df = self._instruments_df
        sub = df[(df['SYMBOL_NAME'] == symbol) & (df['INSTRUMENT_NAME'] == 'OPTFUT') & (df['OPTION_TYPE'] == option_type)]
        if sub.empty:
            # Fallback to base commodity (e.g. NATURALGAS if NATGASMINI options share root)
            base_sym = "NATURALGAS" if "NATGAS" in symbol else ("CRUDEOIL" if "CRUDE" in symbol else symbol)
            sub = df[(df['SYMBOL_NAME'] == base_sym) & (df['INSTRUMENT_NAME'] == 'OPTFUT') & (df['OPTION_TYPE'] == option_type)]
            
        if sub.empty:
            return None

        # Find closest strike
        sub['strike_diff'] = (sub['STRIKE_PRICE'] - atm_strike).abs()
        nearest = sub.sort_values(by=['strike_diff', 'EXPIRY_DATE']).iloc[0]
        
        return {
            "security_id": str(nearest['SECURITY_ID']),
            "scrip_code": f"MCX_{nearest['SECURITY_ID']}",
            "trading_symbol": str(nearest['TRADING_SYMBOL']),
            "strike_price": float(nearest['STRIKE_PRICE']),
            "option_type": str(nearest['OPTION_TYPE']),
            "expiry_date": str(nearest['EXPIRY_DATE']),
            "lot_units": int(nearest['LOT_UNITS'])
        }
