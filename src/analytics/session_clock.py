"""
FinPlus+ MCX Session Clock & Market Phase Classifier
Classifies the 14-hour MCX commodity trading day into institutional phases.
"""

from datetime import datetime
from typing import Dict, Any
from src.utils.time_and_logger import get_ist_now

class MCXSessionClock:
    @staticmethod
    def get_session_info(now_dt: datetime = None) -> Dict[str, Any]:
        if now_dt is None:
            now_dt = get_ist_now()
            
        weekday = now_dt.weekday() # 0=Mon, 4=Fri, 5=Sat, 6=Sun
        hour = now_dt.hour
        minute = now_dt.minute
        time_int = hour * 100 + minute
        
        is_weekend = weekday in (5, 6)
        
        if is_weekend:
            return {
                "is_open": False,
                "phase": "MARKET_CLOSED",
                "phase_label": "MCX: CLOSED (WEEKEND)",
                "trade_permission": False,
                "badge_class": "bg-slate-800 text-slate-400 border-slate-700",
                "guidance": "Commodity exchange closed for weekend. Next session opens Monday 09:00 AM IST.",
                "ist_time": now_dt.strftime("%I:%M:%S %p IST")
            }
            
        # Overnight closure
        if time_int < 900 or time_int >= 2330:
            return {
                "is_open": False,
                "phase": "MARKET_CLOSED",
                "phase_label": "MCX: CLOSED (OVERNIGHT)",
                "trade_permission": False,
                "badge_class": "bg-slate-800 text-slate-400 border-slate-700",
                "guidance": "Overnight session closed. MCX trading reopens at 09:00 AM IST.",
                "ist_time": now_dt.strftime("%I:%M:%S %p IST")
            }
            
        # Mandatory square-off
        if 2315 <= time_int < 2330:
            return {
                "is_open": True,
                "phase": "INTRADAY_SQUARE_OFF",
                "phase_label": "🛑 MANDATORY SQUARE-OFF",
                "trade_permission": False,
                "badge_class": "bg-rose-950 text-rose-300 border-rose-500/50",
                "guidance": "Intraday square-off window active (23:15–23:30 IST). Exit all open MIS positions.",
                "ist_time": now_dt.strftime("%I:%M:%S %p IST")
            }
            
        # US Prime Session (Golden Trading Window)
        if 1800 <= time_int <= 2130:
            return {
                "is_open": True,
                "phase": "US_SESSION_PRIME",
                "phase_label": "🔥 US SESSION PRIME IGNITION",
                "trade_permission": True,
                "badge_class": "bg-emerald-950 text-emerald-300 border-emerald-500/50",
                "guidance": "NYMEX & COMEX pit trading open. Institutional volume active. Highest win-rate window.",
                "ist_time": now_dt.strftime("%I:%M:%S %p IST")
            }
            
        # Pre-US Compression Window
        if 1400 <= time_int < 1730:
            return {
                "is_open": True,
                "phase": "PRE_US_COMPRESSION",
                "phase_label": "📦 PRE-US COMPRESSION",
                "trade_permission": False,
                "badge_class": "bg-amber-950 text-amber-300 border-amber-500/50",
                "guidance": "Volatility coiling. Pre-US high/low compression box establishing. Awaiting US open.",
                "ist_time": now_dt.strftime("%I:%M:%S %p IST")
            }
            
        # Late US Session
        if 2130 < time_int < 2315:
            return {
                "is_open": True,
                "phase": "US_LATE_SESSION",
                "phase_label": "🌙 US LATE CONSOLIDATION",
                "trade_permission": False,
                "badge_class": "bg-blue-950 text-blue-300 border-blue-500/50",
                "guidance": "Late US session. Manage existing positions with trailing stops; no new breakout entries.",
                "ist_time": now_dt.strftime("%I:%M:%S %p IST")
            }
            
        # Morning / Asian session
        return {
            "is_open": True,
            "phase": "ASIAN_MORNING",
            "phase_label": "☕ ASIAN SESSION (STANDBY)",
            "trade_permission": False,
            "badge_class": "bg-slate-800 text-slate-300 border-slate-700",
            "guidance": "Asian morning session. Low liquidity / false breakout chop. Recommended to hold cash until European/US open.",
            "ist_time": now_dt.strftime("%I:%M:%S %p IST")
        }

