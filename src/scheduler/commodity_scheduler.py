"""
FinPlus+ Commodity Scheduler
Executes automated 15-minute quantitative scanning, EIA shield monitoring, and alert dispatch.
"""

import time
import threading
from typing import Dict, Any, List
from datetime import datetime

from config.settings import COMMODITY_SPECS
from src.feeds.commodity_feed import CommodityMarketFeed
from src.feeds.indmoney_commodity_feed import INDMoneyCommodityFeed
from src.analytics.commodity_luxalgo_engine import CommodityLuxAlgoEngine
from src.analytics.commodity_priority_engine import CommodityPriorityEngine
from src.analytics.session_clock import MCXSessionClock
from src.analytics.eia_calendar_shield import EIACalendarShield
from src.notifications.ntfy_dispatcher import CommodityNTFYDispatcher
from src.utils.time_and_logger import setup_logger, get_utc_iso, get_ist_now

logger = setup_logger("CommodityScheduler")

class CommodityScheduler:
    def __init__(self):
        self.feed = CommodityMarketFeed(cache_ttl_seconds=60)
        self.ind_feed = INDMoneyCommodityFeed(cache_ttl_seconds=15)
        self.engine = CommodityLuxAlgoEngine()
        self.ntfy = CommodityNTFYDispatcher()
        
        self.latest_scan_results: Dict[str, Any] = {}
        self.last_scan_time_utc: str = ""
        self.is_running = False
        self._thread: threading.Thread = None

    def run_full_scan(self) -> Dict[str, Any]:
        """
        Executes an instant scan across Crude Oil Mini, Nat Gas Mini, and Gold Petal.
        Grounds live quotes, Open Interest, and contracts strictly on INDstocks API.
        """
        logger.info("Executing comprehensive MCX Commodity scan with INDstocks live broker feed...")
        results = {}
        
        session_info = MCXSessionClock.get_session_info()
        ind_quotes = self.ind_feed.fetch_live_quotes()
        
        for symbol in COMMODITY_SPECS.keys():
            try:
                df = self.feed.fetch_15m_candles(symbol, period="5d")
                analysis = self.engine.analyze_commodity(symbol, df)
                
                # Ground LTP, High, Low, and OI with INDstocks live broker quote
                if symbol in ind_quotes:
                    iq = ind_quotes[symbol]
                    if iq.get("ltp", 0) > 0:
                        analysis["ltp"] = iq["ltp"]
                        analysis["high"] = iq["high"]
                        analysis["low"] = iq["low"]
                        analysis["open_interest"] = iq["open_interest"]
                        analysis["volume"] = iq["volume"]
                        analysis["broker_trading_symbol"] = iq["trading_symbol"]
                        analysis["broker_security_id"] = iq["security_id"]
                        analysis["source"] = "INDstocks Broker API"
                
                # Determine associated Option Directive (CE / PE)
                opt_directive = CommodityPriorityEngine.determine_option_directive(symbol, analysis)
                
                # Attach exact INDstocks option contract details
                if opt_directive.get("type") in ("CALL", "PUT"):
                    opt_type = "CE" if opt_directive["type"] == "CALL" else "PE"
                    atm_strike = opt_directive.get("strike_price", 0)
                    exact_contract = self.ind_feed.find_atm_option_contract(symbol, opt_type, atm_strike)
                    if exact_contract:
                        opt_directive["trading_symbol"] = exact_contract["trading_symbol"]
                        opt_directive["security_id"] = exact_contract["security_id"]
                        opt_directive["scrip_code"] = exact_contract["scrip_code"]
                        opt_directive["contract"] = exact_contract["trading_symbol"]
                        opt_directive["recommended_action"] = f"BUY {exact_contract['trading_symbol']} ({opt_directive['type']})"
                
                analysis["option_directive"] = opt_directive
                results[symbol] = analysis
                
                # If actionable directive during market hours, dispatch NTFY alert
                directive = analysis.get("directive", "")
                if "BUY" in directive or "SELL" in directive:
                    if session_info["is_open"]:
                        self.ntfy.send_breakout_alert(analysis)
            except Exception as e:
                logger.error(f"Error during scan of {symbol}: {e}")
                err_res = self.engine._empty_result(symbol, f"Scan error: {str(e)}")
                err_res["option_directive"] = CommodityPriorityEngine.determine_option_directive(symbol, err_res)
                results[symbol] = err_res

        # Select the single #1 Best Commodity to Trade right now
        priority_trade = CommodityPriorityEngine.select_priority_commodity(results)

        self.latest_scan_results = {
            "timestamp_utc": get_utc_iso(),
            "timestamp_ist": get_ist_now().strftime("%I:%M:%S %p IST"),
            "session": session_info,
            "priority_trade": priority_trade,
            "commodities": results
        }
        self.last_scan_time_utc = self.latest_scan_results["timestamp_utc"]
        logger.info("Scan completed successfully across all 3 commodity derivatives.")
        return self.latest_scan_results

    def start_background_loop(self, interval_seconds: int = 60):
        """Starts background monitoring loop."""
        if self.is_running:
            return
            
        self.is_running = True
        
        def _loop():
            logger.info(f"Commodity background daemon started (polling interval: {interval_seconds}s)")
            # Run initial scan immediately
            self.run_full_scan()
            
            while self.is_running:
                try:
                    time.sleep(interval_seconds)
                    session = MCXSessionClock.get_session_info()
                    # If MCX is open, run scheduled refresh
                    if session["is_open"]:
                        self.run_full_scan()
                except Exception as e:
                    logger.error(f"Error in background scheduler loop: {e}")
                    
        self._thread = threading.Thread(target=_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stops background loop."""
        self.is_running = False

