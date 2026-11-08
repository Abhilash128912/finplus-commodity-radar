"""
FinPlus+ Commodity Priority & Options Strike Engine
1. Selects the single #1 Best Commodity to Trade right now among Crude Mini, NatGas Mini, and Gold Petal.
2. Computes the exact ATM Option Strike (CE for Bullish Breakout, PE for Bearish Breakdown).
3. Enforces strict zero-simultaneous CE/PE gating and theta protection during range consolidation.
"""

from typing import Dict, Any, List, Optional
import math
from src.utils.time_and_logger import setup_logger

logger = setup_logger("CommodityPriorityEngine")

# MCX Option Contract Strike Step specifications
COMMODITY_OPTION_SPECS = {
    "CRUDEOILM": {
        "option_symbol_prefix": "CRUDEOIL",
        "strike_step": 50, # Strike intervals: 8400, 8450, 8500, 8550
        "option_lot_size": 100, # Barrels per standard option lot
        "tick_size": 0.05,
        "description": "MCX Crude Oil Monthly Options"
    },
    "NATGASMINI": {
        "option_symbol_prefix": "NATGAS",
        "strike_step": 5, # Strike intervals: 270, 275, 280, 285
        "option_lot_size": 1250, # mmBtu per standard option lot
        "tick_size": 0.05,
        "description": "MCX Natural Gas Monthly Options"
    },
    "GOLDPETAL": {
        "option_symbol_prefix": "GOLDM",
        "strike_step": 500, # Gold Mini Option strike step
        "option_lot_size": 100, # Grams (Gold Mini)
        "tick_size": 0.50,
        "description": "MCX Gold Mini Options / Gold Petal Direct"
    }
}

class CommodityPriorityEngine:
    @staticmethod
    def calculate_atm_strike(ltp: float, strike_step: int) -> int:
        """Rounds LTP to nearest ATM strike step."""
        if ltp <= 0 or strike_step <= 0:
            return 0
        return int(round(ltp / strike_step) * strike_step)

    @staticmethod
    def determine_option_directive(symbol: str, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculates the single confirmed Option Strike (CE or PE) based strictly on market breakout direction.
        Never outputs CE and PE simultaneously.
        """
        opt_spec = COMMODITY_OPTION_SPECS.get(symbol, {})
        prefix = opt_spec.get("option_symbol_prefix", symbol)
        step = opt_spec.get("strike_step", 50)
        lot_size = opt_spec.get("option_lot_size", 100)
        
        ltp = analysis.get("ltp", 0.0)
        directive = analysis.get("directive", "")
        eia = analysis.get("eia_info", {})
        session = analysis.get("session_info", {})
        
        atm_strike = CommodityPriorityEngine.calculate_atm_strike(ltp, step)
        
        # 1. EIA Shield Active -> Zero Options
        if eia.get("shield_active", False):
            return {
                "recommended_action": "HOLD CASH (EIA SHIELD)",
                "contract": "NONE",
                "strike_name": "NONE (EIA SHIELD ACTIVE)",
                "type": "NONE",
                "strike_price": atm_strike,
                "badge_class": "bg-rose-950/80 border-rose-500/60 text-rose-300",
                "lot_size": lot_size,
                "advice": "Trading frozen around inventory release to avoid extreme option spread slippage."
            }
            
        # 2. Bullish Breakout -> BUY CE
        if "BUY LONG" in directive:
            contract_name = f"{prefix} {atm_strike} CE"
            box_top = analysis.get('box_top')
            ref_str = f"above {box_top:,.2f}" if box_top is not None else "above resistance"
            return {
                "recommended_action": f"BUY {contract_name} (CALL)",
                "contract": contract_name,
                "strike_name": contract_name,
                "type": "CALL",
                "strike_price": atm_strike,
                "badge_class": "bg-emerald-950 border-emerald-500/60 text-emerald-300 animate-pulse",
                "lot_size": lot_size,
                "sl_rule": "Exit if underlying futures breaks below Box Midline",
                "target_rule": "Target 1: +50% Option Premium | Target 2: +100% Option Premium",
                "advice": f"Confirmed bullish breakout {ref_str} with 20/50 EMA & Volume support."
            }
            
        # 3. Bearish Breakdown -> BUY PE
        elif "SELL SHORT" in directive:
            contract_name = f"{prefix} {atm_strike} PE"
            box_bot = analysis.get('box_bottom')
            ref_str = f"below {box_bot:,.2f}" if box_bot is not None else "below support"
            return {
                "recommended_action": f"BUY {contract_name} (PUT)",
                "contract": contract_name,
                "strike_name": contract_name,
                "type": "PUT",
                "strike_price": atm_strike,
                "badge_class": "bg-rose-950 border-rose-500/60 text-rose-300 animate-pulse",
                "lot_size": lot_size,
                "sl_rule": "Exit if underlying futures recovers above Box Midline",
                "target_rule": "Target 1: +50% Option Premium | Target 2: +100% Option Premium",
                "advice": f"Confirmed bearish breakdown {ref_str} with 20/50 EMA & Volume support."
            }
            
        # 4. Range Consolidation -> Standby (Theta Protection)
        return {
            "recommended_action": "HOLD CASH / DO NOT BUY OPTIONS",
            "contract": "NONE",
            "strike_name": f"ATM Watch: {prefix} {atm_strike}",
            "type": "NONE",
            "strike_price": atm_strike,
            "badge_class": "bg-slate-900 border-slate-800 text-slate-400",
            "lot_size": lot_size,
            "sl_rule": "--",
            "target_rule": "--",
            "advice": "Price is inside 15m compression box. Options will suffer theta decay. Await confirmed boundary breakout."
        }

    @staticmethod
    def select_priority_commodity(commodities_analysis: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Ranks all 3 commodities and picks the single #1 Best to Trade right now.
        """
        candidates = []
        
        for symbol, data in commodities_analysis.items():
            directive = data.get("directive", "")
            score = data.get("confluence_score", 0)
            eia = data.get("eia_info", {})
            session = data.get("session_info", {})
            box_width = data.get("box_width_pct", 5.0)
            
            # Penalize if shielded
            if eia.get("shield_active", False):
                effective_score = -100
            else:
                effective_score = score
                # Bonus for active breakout
                if "BUY" in directive or "SELL" in directive:
                    effective_score += 50
                # Bonus for tight compression ready to burst
                if box_width < 2.0:
                    effective_score += 15
                    
            candidates.append({
                "symbol": symbol,
                "data": data,
                "effective_score": effective_score,
                "is_active_breakout": ("BUY" in directive or "SELL" in directive)
            })
            
        # Sort candidates
        candidates.sort(key=lambda x: (x["is_active_breakout"], x["effective_score"]), reverse=True)
        
        best = candidates[0] if candidates else None
        if not best:
            return {"symbol": None, "priority_label": "NO ACTIVE CANDIDATE"}
            
        best_data = best["data"]
        best_sym = best["symbol"]
        
        # Attach the exact option directive
        opt_directive = CommodityPriorityEngine.determine_option_directive(best_sym, best_data)
        
        status_label = "🔥 ACTIVE BREAKOUT IGNITION" if best["is_active_breakout"] else "👀 TOP COILING COMPRESSION (PRIME WATCH)"
        
        return {
            "symbol": best_sym,
            "display_name": best_data.get("display_name", best_sym),
            "lot_unit": best_data.get("lot_unit", "1 Lot"),
            "priority_status": status_label,
            "confluence_score": best_data.get("confluence_score", 0),
            "ltp": best_data.get("ltp", 0.0),
            "futures_directive": best_data.get("directive", "STANDBY"),
            "option_directive": opt_directive,
            "entry_trigger": best_data.get("entry_price"),
            "stop_loss": best_data.get("stop_loss"),
            "target_1": best_data.get("target_1"),
            "target_2": best_data.get("target_2"),
            "risk_per_lot_inr": best_data.get("risk_per_lot_inr", 0.0),
            "gain_per_lot_inr": best_data.get("gain_per_lot_inr", 0.0),
            "reason": best_data.get("reason", ""),
            "eia_status": best_data.get("eia_info", {}).get("status", "CLEAR")
        }
