"""
FinPlus+ Commodity NTFY Alert Dispatcher
Dispatches rich mobile alerts for MCX Mini/Petal breakouts, EIA shields, and square-off timers.
Target: https://ntfy.sh/Finplus-Commodity
"""

import time
import requests
from typing import Dict, Any, Optional
from config.settings import NTFY_TOPIC, NTFY_SERVER
from src.utils.time_and_logger import setup_logger, get_ist_now

logger = setup_logger("CommodityNTFY")

class CommodityNTFYDispatcher:
    def __init__(self, topic: str = NTFY_TOPIC, server: str = NTFY_SERVER):
        self.topic = topic
        self.url = f"{server.rstrip('/')}/{topic}"
        self._last_alert_time: Dict[str, float] = {}

    def send_breakout_alert(self, analysis: Dict[str, Any], force: bool = False) -> bool:
        """
        Sends an actionable strike alert when a commodity breaks out of compression with 20/50 EMA confirmation.
        """
        symbol = analysis.get("symbol", "UNKNOWN")
        directive = analysis.get("directive", "STANDBY")
        
        if "BUY" not in directive and "SELL" not in directive:
            return False
            
        now = time.time()
        # 30-minute anti-spam per symbol
        if not force and symbol in self._last_alert_time:
            if (now - self._last_alert_time[symbol]) < 1800:
                logger.info(f"Skipping NTFY alert for {symbol} (rate-limited, sent < 30m ago)")
                return False

        display_name = analysis.get("display_name", symbol)
        lot_unit = analysis.get("lot_unit", "1 Lot")
        entry = analysis.get("entry_price", 0.0)
        sl = analysis.get("stop_loss", 0.0)
        t1 = analysis.get("target_1", 0.0)
        t2 = analysis.get("target_2", 0.0)
        risk_rs = analysis.get("risk_per_lot_inr", 0.0)
        gain_rs = analysis.get("gain_per_lot_inr", 0.0)
        score = analysis.get("confluence_score", 0)
        reason = analysis.get("reason", "")
        
        is_long = "LONG" in directive or "BUY" in directive
        emoji = "🟢🚀" if is_long else "🔴⚡"
        action = "BUY LONG" if is_long else "SELL SHORT"
        
        opt = analysis.get("option_directive", {})
        opt_str = opt.get("recommended_action", "NONE")
        
        title = f"{emoji} {display_name}: {action} (Score: {score}/100)"
        
        message = (
            f"🎯 FUTURES DIRECTIVE: {action} ({lot_unit})\n"
            f"🎫 OPTION STRIKE: {opt_str}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"• Entry Trigger: ₹{entry:,.2f}\n"
            f"• Stop Loss: ₹{sl:,.2f} (-₹{risk_rs:,.0f}/lot)\n"
            f"• Target 1 (1:1.5): ₹{t1:,.2f} (+₹{gain_rs:,.0f}/lot)\n"
            f"• Target 2 (1:2.0): ₹{t2:,.2f}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"• Confluence: {score}/100 (LuxAlgo + 20/50 EMA + Vol)\n"
            f"• Context: {reason}\n"
            f"• Time: {get_ist_now().strftime('%I:%M:%S %p IST')}"
        )
        
        headers = {
            "Title": title,
            "Priority": "high",
            "Tags": "chart_with_upwards_trend,moneybag" if is_long else "chart_with_downwards_trend,warning",
            "Click": "http://127.0.0.1:8002"
        }
        
        try:
            res = requests.post(self.url, data=message.encode("utf-8"), headers=headers, timeout=5)
            if res.status_code == 200:
                self._last_alert_time[symbol] = now
                logger.info(f"NTFY alert successfully sent for {symbol}: {title}")
                return True
            else:
                logger.warning(f"NTFY returned status {res.status_code}: {res.text}")
        except Exception as e:
            logger.error(f"Failed to post to NTFY ({self.url}): {e}")
            
        return False

    def send_system_pulse(self, message: str, title: str = "FinPlus+ Commodity Sentry") -> bool:
        """Sends administrative / status pulse to NTFY."""
        headers = {
            "Title": title,
            "Priority": "default",
            "Tags": "information_source,oil_drum",
            "Click": "http://127.0.0.1:8002"
        }
        try:
            res = requests.post(self.url, data=message.encode("utf-8"), headers=headers, timeout=5)
            return res.status_code == 200
        except Exception as e:
            logger.error(f"Failed to send system pulse to NTFY: {e}")
            return False

