"""
FinPlus+ Commodity NTFY Alert Dispatcher
Dispatches rich mobile alerts for MCX Mini/Petal breakouts, EIA shields, and square-off timers.
Delivers redundancy to both Finplus-Delta and Finplus-Commodity topics.
Target: https://ntfy.sh/Finplus-Delta, https://ntfy.sh/Finplus-Commodity
"""

import os
import time
import requests
from typing import Dict, Any, Optional, List
from config.settings import NTFY_SERVER
from src.utils.time_and_logger import setup_logger, get_ist_now

logger = setup_logger("CommodityNTFY")

RENDER_COMMODITY_URL = "https://finplus-commodity-radar.onrender.com"
DEFAULT_TOPICS = ["Finplus-Delta", "Finplus-Commodity"]

class CommodityNTFYDispatcher:
    def __init__(self, topics: Optional[List[str]] = None, server: str = NTFY_SERVER):
        env_topic = os.getenv("NTFY_TOPIC")
        if env_topic:
            self.topics = [env_topic.strip()]
            if "Finplus-Delta" not in self.topics:
                self.topics.append("Finplus-Delta")
        elif topics:
            self.topics = topics
        else:
            self.topics = DEFAULT_TOPICS

        self.server = server.rstrip("/")
        self._last_alert_time: Dict[str, float] = {}

    def send_breakout_alert(self, analysis: Dict[str, Any], force: bool = False) -> bool:
        """
        Sends an actionable strike alert when a commodity breaks out of compression with 20/50 EMA confirmation.
        """
        from datetime import datetime, timezone, timedelta
        ist_now = datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)
        if not force and ist_now.weekday() >= 5: # Saturday/Sunday
            logger.info("Weekend detected. Skipping MCX commodity alert.")
            return False

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
        action = "BUY LONG" if is_long else "SELL SHORT"
        
        opt = analysis.get("option_directive", {})
        opt_str = opt.get("recommended_action", "NONE")
        
        title = f"{display_name}: {action} (Score: {score}/100)"
        
        lines = [
            f"**FINPLUS+ MCX COMMODITY BREAKOUT**",
            f"`{display_name} | {action}`",
            "----------------------------------------",
            f"• Futures Directive: `{action}` ({lot_unit})",
            f"• Option Strike: `{opt_str}`",
            "",
            "**EXECUTION PARAMETERS**",
            f"• Entry Trigger: Rs {entry:,.2f}",
            f"• Stop Loss: Rs {sl:,.2f} (-Rs {risk_rs:,.0f}/lot)",
            f"• Target 1 (1:1.5): Rs {t1:,.2f} (+Rs {gain_rs:,.0f}/lot)",
            f"• Target 2 (1:2.0): Rs {t2:,.2f}",
            f"• Confluence: {score}/100 (LuxAlgo + 20/50 EMA + Volume)",
            f"• Setup: {reason}",
            f"• Time: {get_ist_now().strftime('%I:%M:%S %p IST')}",
            "----------------------------------------",
            f"Cockpit: {RENDER_COMMODITY_URL}"
        ]
        
        message = "\n".join(lines)
        
        headers = {
            "Title": title,
            "Priority": "high",
            "Markdown": "yes",
            "X-Markdown": "yes",
            "Click": RENDER_COMMODITY_URL,
            "Actions": f"view, Open Commodity Radar, {RENDER_COMMODITY_URL}"
        }
        
        any_success = False
        for topic in self.topics:
            url = f"{self.server}/{topic}"
            try:
                res = requests.post(url, data=message.encode("utf-8"), headers=headers, timeout=5)
                if res.status_code == 200:
                    self._last_alert_time[symbol] = now
                    logger.info(f"NTFY alert successfully sent to '{topic}' for {symbol}: {title}")
                    any_success = True
                else:
                    logger.warning(f"NTFY returned status {res.status_code} for '{topic}': {res.text}")
            except Exception as e:
                logger.error(f"Failed to post to NTFY ({url}): {e}")
                
        return any_success

    def send_system_pulse(self, message: str, title: str = "FinPlus+ Commodity Sentry") -> bool:
        """Sends administrative / status pulse to NTFY across registered topics."""
        headers = {
            "Title": title,
            "Priority": "default",
            "Tags": "information_source,oil_drum",
            "Markdown": "yes",
            "X-Markdown": "yes",
            "Click": RENDER_COMMODITY_URL,
            "Actions": f"view, Open Commodity Radar, {RENDER_COMMODITY_URL}"
        }
        any_success = False
        for topic in self.topics:
            url = f"{self.server}/{topic}"
            try:
                res = requests.post(url, data=message.encode("utf-8"), headers=headers, timeout=5)
                if res.status_code == 200:
                    any_success = True
            except Exception as e:
                logger.error(f"Failed to send system pulse to NTFY ({url}): {e}")
        return any_success
