"""
FinPlus+ EIA Inventory Calendar & News Shield
Prevents costly slippage & spread blowouts around weekly US Energy Information Administration releases.
- Wednesday 20:00 IST: Weekly Petroleum Status Report (Crude Oil)
- Thursday 20:00 IST: Weekly Natural Gas Storage Report (Natural Gas)
"""

from datetime import datetime
from typing import Dict, Any
from src.utils.time_and_logger import get_ist_now

class EIACalendarShield:
    @staticmethod
    def get_shield_status(symbol: str, now_dt: datetime = None) -> Dict[str, Any]:
        """
        Evaluates whether the EIA News Shield should freeze new trading entries for the given symbol.
        """
        if now_dt is None:
            now_dt = get_ist_now()
            
        weekday = now_dt.weekday() # 2=Wednesday, 3=Thursday
        hour = now_dt.hour
        minute = now_dt.minute
        time_int = hour * 100 + minute
        
        is_crude = (symbol == "CRUDEOILM")
        is_natgas = (symbol == "NATGASMINI")
        
        # Gold is not directly governed by EIA weekly inventories
        if not is_crude and not is_natgas:
            return {
                "shield_active": False,
                "status": "CLEAR",
                "badge_class": "text-slate-400 bg-slate-800/40 border-slate-700",
                "message": "N/A (Metals not subject to EIA storage reports)",
                "next_event": "FOMC / US CPI / Non-Farm Payrolls"
            }
            
        # Target day & time:
        # Wednesday (weekday 2) for Crude
        # Thursday (weekday 3) for Natgas
        event_weekday = 2 if is_crude else 3
        event_name = "EIA Petroleum Inventory" if is_crude else "EIA Natural Gas Storage"
        
        if weekday == event_weekday:
            # Shield freezes entries between 19:55 and 20:05 IST
            if 1955 <= time_int <= 2005:
                return {
                    "shield_active": True,
                    "status": "SHIELD_ACTIVE",
                    "badge_class": "text-rose-300 bg-rose-950/80 border-rose-500/60 animate-pulse",
                    "message": f"🚨 EIA SHIELD ACTIVE ({event_name}). Trading frozen until 20:05 IST to avoid spread blowouts.",
                    "next_event": f"Report releasing NOW ({now_dt.strftime('%I:%M %p')})"
                }
            elif 1800 <= time_int < 1955:
                mins_left = (19 * 60 + 55) - (hour * 60 + minute)
                return {
                    "shield_active": False,
                    "status": "UPCOMING",
                    "badge_class": "text-amber-300 bg-amber-950/80 border-amber-500/60",
                    "message": f"⚠️ {event_name} due in {mins_left} mins (20:00 IST). Prepare for elevated volatility.",
                    "next_event": f"Today at 08:00 PM IST"
                }
            elif 2005 < time_int <= 2030:
                return {
                    "shield_active": False,
                    "status": "POST_RELEASE",
                    "badge_class": "text-emerald-300 bg-emerald-950/80 border-emerald-500/60",
                    "message": f"✅ {event_name} landed. Institutional direction confirmed; normal trading resumed.",
                    "next_event": "Complete for this week"
                }
                
        # Non-event days / outside window
        days_ahead = (event_weekday - weekday) % 7
        day_str = "Wednesday" if is_crude else "Thursday"
        return {
            "shield_active": False,
            "status": "CLEAR",
            "badge_class": "text-emerald-400 bg-emerald-950/30 border-emerald-600/30",
            "message": f"Clear • Next {event_name}: {day_str} 08:00 PM IST",
            "next_event": f"{day_str} 08:00 PM IST"
        }

