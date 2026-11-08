"""
FinPlus+ Commodity Market Data Feed
Fetches live continuous 15m/5m candle data for WTI Crude Oil, Henry Hub Natural Gas, and COMEX Gold.
Converts international dollar futures into MCX Rupee equivalents using live USD/INR exchange rates.
"""

import time
import pandas as pd
import yfinance as yf
from typing import Dict, Any, Optional

from config.settings import COMMODITY_SPECS
from src.utils.time_and_logger import setup_logger

logger = setup_logger("CommodityFeed")

class CommodityMarketFeed:
    def __init__(self, cache_ttl_seconds: int = 60):
        self.cache_ttl = cache_ttl_seconds
        self._candle_cache: Dict[str, Any] = {}
        self._usdinr_cache: Dict[str, Any] = {}

    def get_usdinr_rate(self) -> float:
        """Fetches live USD/INR exchange rate with 5-minute cache."""
        now = time.time()
        if "rate" in self._usdinr_cache and (now - self._usdinr_cache.get("time", 0)) < 300:
            return self._usdinr_cache["rate"]
            
        try:
            df = yf.download("USDINR=X", period="1d", interval="15m", progress=False)
            if not df.empty:
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = [col[0] for col in df.columns]
                rate = float(df['Close'].dropna().iloc[-1])
                self._usdinr_cache = {"rate": rate, "time": now}
                logger.info(f"USD/INR exchange rate updated: ₹{rate:.2f}")
                return rate
        except Exception as e:
            logger.warning(f"Failed to fetch live USD/INR, using fallback ₹88.50: {e}")
            
        return 88.50

    def fetch_15m_candles(self, symbol: str, period: str = "5d") -> pd.DataFrame:
        """
        Fetches 15-minute candles for the commodity benchmark.
        Converts dollar prices to MCX Rupee pricing.
        """
        spec = COMMODITY_SPECS.get(symbol)
        if not spec:
            logger.error(f"Unknown commodity symbol: {symbol}")
            return pd.DataFrame()
            
        ticker = spec["benchmark_ticker"]
        cache_key = f"{symbol}_15m_{period}"
        now = time.time()
        
        # Check cache
        if cache_key in self._candle_cache:
            entry = self._candle_cache[cache_key]
            if (now - entry["timestamp"]) < self.cache_ttl:
                return entry["data"].copy()
                
        try:
            df = yf.download(ticker, period=period, interval="15m", progress=False)
            if df.empty and period != "1mo":
                # Fallback to 1mo if 5d is empty (e.g. contract rollover or weekend gap)
                logger.info(f"Retrying {ticker} with period='1mo' due to contract rollover gap...")
                df = yf.download(ticker, period="1mo", interval="15m", progress=False)
                
            if df.empty:
                logger.warning(f"No data returned for ticker {ticker}")
                return pd.DataFrame()
                
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [col[0] for col in df.columns]
                
            df = df.dropna().copy()
            usdinr = self.get_usdinr_rate()
            
            # Convert dollar benchmark to approximate MCX Rupee prices
            if symbol == "CRUDEOILM":
                # WTI Crude $/bbl * USDINR = ₹ / bbl
                conversion_factor = usdinr
            elif symbol == "NATGASMINI":
                # Henry Hub $/mmBtu * USDINR = ₹ / mmBtu
                conversion_factor = usdinr
            elif symbol == "GOLDPETAL":
                # COMEX Gold $/troy oz * USDINR / 31.1035 * 1.15 (import duty/GST) = ₹ / gram
                conversion_factor = (usdinr / 31.1034768) * 1.15
            else:
                conversion_factor = 1.0
                
            df['Close_USD'] = df['Close']
            df['Close'] = df['Close'] * conversion_factor
            df['High'] = df['High'] * conversion_factor
            df['Low'] = df['Low'] * conversion_factor
            df['Open'] = df['Open'] * conversion_factor
            
            self._candle_cache[cache_key] = {"data": df, "timestamp": now}
            logger.info(f"Loaded {len(df)} candles for {symbol} ({ticker}) at ₹{df['Close'].iloc[-1]:,.2f}")
            return df.copy()
            
        except Exception as e:
            logger.error(f"Error fetching candles for {symbol} ({ticker}): {e}")
            if cache_key in self._candle_cache:
                return self._candle_cache[cache_key]["data"].copy()
            return pd.DataFrame()

    def get_live_quote(self, symbol: str) -> Dict[str, Any]:
        """Returns the latest quote and daily percentage change."""
        df = self.fetch_15m_candles(symbol, period="5d")
        if df.empty:
            return {"ltp": 0.0, "change_pct": 0.0, "high": 0.0, "low": 0.0}
            
        last_close = float(df['Close'].iloc[-1])
        prev_close = float(df['Close'].iloc[-2]) if len(df) > 1 else last_close
        chg_pct = ((last_close - prev_close) / prev_close) * 100.0 if prev_close > 0 else 0.0
        
        return {
            "ltp": round(last_close, 2),
            "change_pct": round(chg_pct, 2),
            "high": round(float(df['High'].max()), 2),
            "low": round(float(df['Low'].min()), 2),
            "volume": int(df['Volume'].iloc[-1])
        }

