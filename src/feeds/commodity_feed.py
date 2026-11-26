"""
FinPlus+ Commodity Market Data Feed (100% INDstocks / INDmoney Broker API)
Fetches MCX 15m historical candles and live quotes directly in INR via INDstocks API.
Zero yfinance dependency.
"""

import time
import datetime
import pandas as pd
import requests
from typing import Dict, Any, Optional

from config.settings import COMMODITY_SPECS
from src.feeds.indmoney_commodity_feed import ACTIVE_MCX_CONTRACTS, INDMoneyCommodityFeed
from src.utils.time_and_logger import setup_logger

logger = setup_logger("CommodityFeed")


class CommodityMarketFeed:
    BASE_URL = "https://api.indstocks.com"
    HISTORICAL_ENDPOINT = "/market/historical-data"

    def __init__(self, cache_ttl_seconds: int = 60, ind_feed: Optional[INDMoneyCommodityFeed] = None):
        self.cache_ttl = cache_ttl_seconds
        self._candle_cache: Dict[str, Any] = {}
        self._rolling_bars: Dict[str, list] = {}
        self.ind_feed = ind_feed

    def _get_ind_feed(self) -> INDMoneyCommodityFeed:
        if self.ind_feed is None:
            self.ind_feed = INDMoneyCommodityFeed(cache_ttl_seconds=15)
        return self.ind_feed

    def fetch_15m_candles(self, symbol: str, period: str = "5d") -> pd.DataFrame:
        """
        Fetches 15-minute MCX candles directly in INR from INDstocks /market/historical-data,
        falling back to rolling 15m bars synthesized from INDstocks live /market/quotes/full.
        """
        if symbol not in COMMODITY_SPECS and symbol not in ACTIVE_MCX_CONTRACTS:
            logger.error(f"Unknown commodity symbol: {symbol}")
            return pd.DataFrame()

        cache_key = f"{symbol}_15m_{period}"
        now = time.time()
        if cache_key in self._candle_cache:
            entry = self._candle_cache[cache_key]
            if (now - entry["timestamp"]) < self.cache_ttl:
                return entry["data"].copy()

        meta = ACTIVE_MCX_CONTRACTS.get(symbol)
        if not meta:
            return pd.DataFrame()

        ind_feed = self._get_ind_feed()
        days = 30 if period == "1mo" else 5
        end_dt = datetime.datetime.now(datetime.timezone.utc)
        start_dt = end_dt - datetime.timedelta(days=days)

        try:
            headers = ind_feed._get_valid_headers()
            params = {
                "scrip-code": meta["scrip_code"],
                "interval": "15m",
                "start-time": start_dt.strftime("%Y-%m-%d %H:%M:%S"),
                "end-time": end_dt.strftime("%Y-%m-%d %H:%M:%S"),
            }
            resp = requests.get(
                f"{self.BASE_URL}{self.HISTORICAL_ENDPOINT}",
                headers=headers,
                params=params,
                timeout=5.0,
            )
            if resp.status_code == 200:
                payload = resp.json()
                candles = payload.get("data", {}).get("candles") or payload.get("candles") or []
                if candles:
                    df = pd.DataFrame(candles)
                    rename_map = {
                        "open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume",
                        "o": "Open", "h": "High", "l": "Low", "c": "Close", "v": "Volume",
                    }
                    df = df.rename(columns=rename_map)
                    if all(c in df.columns for c in ("Open", "High", "Low", "Close")):
                        if "Volume" not in df.columns:
                            df["Volume"] = 0
                        for c in ("Open", "High", "Low", "Close", "Volume"):
                            df[c] = pd.to_numeric(df[c], errors="coerce")
                        df = df.dropna(subset=["Open", "High", "Low", "Close"]).copy()
                        if not df.empty:
                            self._candle_cache[cache_key] = {"data": df, "timestamp": now}
                            return df.copy()
        except Exception as e:
            logger.debug(f"INDstocks historical candles unavailable for {symbol}: {e}")

        # Fallback: synthesize rolling bar from live INDstocks quote
        quotes = ind_feed.fetch_live_quotes()
        q = quotes.get(symbol)
        if q and q.get("ltp", 0) > 0:
            bar = {
                "Open": float(q.get("open") or q["ltp"]),
                "High": float(q.get("high") or q["ltp"]),
                "Low": float(q.get("low") or q["ltp"]),
                "Close": float(q["ltp"]),
                "Volume": int(q.get("volume") or 0),
            }
            buf = self._rolling_bars.setdefault(symbol, [])
            buf.append(bar)
            if len(buf) > 100:
                del buf[:-100]
            df = pd.DataFrame(buf)
            self._candle_cache[cache_key] = {"data": df, "timestamp": now}
            return df.copy()

        return pd.DataFrame()
