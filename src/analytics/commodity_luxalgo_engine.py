"""
FinPlus+ Commodity LuxAlgo Quantitative Engine
15-Minute Range Compression + 20/50 EMA Trend Gate + Volume Expansion.
Specifically calibrated for MCX Mini/Petal contracts (Crude Mini, NatGas Mini, Gold Petal).
"""

import math
import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple

from config.settings import (
    LUXALGO_LOOKBACK,
    LUXALGO_ATR_PERIOD,
    LUXALGO_ATR_MULT,
    EMA_FAST_PERIOD,
    EMA_TREND_PERIOD,
    VOLUME_EXPANSION_THRESHOLD,
    RISK_REWARD_RATIO,
    MAX_STOP_LOSS_PCT,
    COMMODITY_SPECS
)
from src.analytics.session_clock import MCXSessionClock
from src.analytics.eia_calendar_shield import EIACalendarShield

def calc_rma(series: pd.Series, length: int) -> pd.Series:
    alpha = 1.0 / length
    return series.ewm(alpha=alpha, adjust=False).mean()

def calc_atr(df: pd.DataFrame, length: int = 200) -> pd.Series:
    high = df['High']
    low = df['Low']
    close = df['Close']
    prev_close = close.shift(1)
    
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    eff_len = min(length, max(14, len(df) // 2))
    return calc_rma(tr, eff_len)

class CommodityLuxAlgoEngine:
    def __init__(
        self,
        lookback: int = LUXALGO_LOOKBACK,
        atr_period: int = LUXALGO_ATR_PERIOD,
        atr_mult: float = LUXALGO_ATR_MULT
    ):
        self.lookback = lookback
        self.atr_period = atr_period
        self.atr_mult = atr_mult

    def analyze_commodity(self, symbol: str, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Runs comprehensive quantitative analysis on 15m candle dataframe for a commodity.
        """
        spec = COMMODITY_SPECS.get(symbol, {})
        rupee_mult = spec.get("rupee_multiplier_per_point", 1.0)
        lot_unit = spec.get("lot_unit", "1 Lot")
        
        if df.empty or len(df) < 50:
            return self._empty_result(symbol, "Insufficient candle history for analysis")

        df = df.copy()
        
        # Calculate Technical Indicators
        df['ema20'] = df['Close'].ewm(span=EMA_FAST_PERIOD, adjust=False).mean()
        df['ema50'] = df['Close'].ewm(span=EMA_TREND_PERIOD, adjust=False).mean()
        df['vol_ma'] = df['Volume'].rolling(20).mean()
        df['atr'] = calc_atr(df, self.atr_period) * self.atr_mult
        
        # LuxAlgo Box Boundaries (Rolling mean of lookback)
        ma = df['Close'].rolling(self.lookback).mean()
        atr = df['atr']
        
        n_bars = len(df)
        closes = df['Close'].values
        highs = df['High'].values
        lows = df['Low'].values
        volumes = df['Volume'].values
        vol_mas = df['vol_ma'].values
        ema20s = df['ema20'].values
        ema50s = df['ema50'].values
        ma_vals = ma.values
        atr_vals = atr.values
        
        # State tracking
        bx_top = np.nan
        bx_bottom = np.nan
        bx_mid = np.nan
        bx_right = -1
        is_compressed = False
        
        for n in range(self.lookback, n_bars):
            curr_ma = ma_vals[n]
            curr_atr = atr_vals[n]
            if np.isnan(curr_ma) or np.isnan(curr_atr):
                continue
                
            count = 0
            for i in range(self.lookback):
                bar_idx = n - i
                if abs(closes[bar_idx] - curr_ma) > curr_atr:
                    count += 1
                    
            if count == 0:
                is_compressed = True
                bx_top = curr_ma + curr_atr
                bx_bottom = curr_ma - curr_atr
                bx_mid = curr_ma
                bx_right = n
            elif n > bx_right + 12:
                is_compressed = False
                
        last_close = float(closes[-1])
        last_high = float(highs[-1])
        last_low = float(lows[-1])
        last_vol = float(volumes[-1])
        last_vol_ma = float(vol_mas[-1]) if not np.isnan(vol_mas[-1]) else 1.0
        last_ema20 = float(ema20s[-1])
        last_ema50 = float(ema50s[-1])
        
        # Fallback if no box recently active
        if np.isnan(bx_top):
            bx_top = max(highs[-16:])
            bx_bottom = min(lows[-16:])
            bx_mid = (bx_top + bx_bottom) / 2.0
            
        box_width_pct = ((bx_top - bx_bottom) / last_close) * 100.0
        
        # Session and EIA Shield Checks
        session_info = MCXSessionClock.get_session_info()
        eia_info = EIACalendarShield.get_shield_status(symbol)
        
        # Confluence Scoring (0 - 100)
        # 1. Compression (35 pts): tight consolidation < 2.5% band
        compression_pts = 35 if (box_width_pct <= 2.5) else (20 if box_width_pct <= 3.5 else 5)
        
        # 2. EMA Trend Gate (30 pts):
        bull_trend = (last_close > last_ema20 and last_close > last_ema50)
        bear_trend = (last_close < last_ema20 and last_close < last_ema50)
        trend_pts = 30 if (bull_trend or bear_trend) else 10
        
        # 3. Volume Expansion (20 pts):
        vol_ratio = (last_vol / last_vol_ma) if last_vol_ma > 0 else 1.0
        volume_pts = 20 if (vol_ratio >= VOLUME_EXPANSION_THRESHOLD) else (10 if vol_ratio >= 1.0 else 0)
        
        # 4. US Session Alignment (15 pts):
        is_us_prime = (session_info["phase"] == "US_SESSION_PRIME")
        session_pts = 15 if is_us_prime else (5 if session_info["is_open"] else 0)
        
        total_score = compression_pts + trend_pts + volume_pts + session_pts
        
        # Directives
        directive = "HOLD CASH / STANDBY"
        reason = "Consolidating inside compression box"
        entry_price = None
        stop_loss = None
        target_1 = None
        target_2 = None
        risk_per_lot = 0.0
        gain_per_lot = 0.0
        
        # EIA News Shield Veto
        # Pre-Ignition Launchpad Squeeze Gate for Commodities (Crude, NatGas, Gold)
        dist_to_top_pct = round(((bx_top - last_close) / max(1.0, bx_top)) * 100.0, 2)
        dist_to_bot_pct = round(((last_close - bx_bottom) / max(1.0, bx_bottom)) * 100.0, 2)
        is_pre_ignition_long = (0.0 <= dist_to_top_pct <= 0.5) and bull_trend and session_info["is_open"]
        is_pre_ignition_short = (0.0 <= dist_to_bot_pct <= 0.5) and bear_trend and session_info["is_open"]

        if eia_info["shield_active"]:
            directive = "PAUSED (EIA NEWS SHIELD)"
            reason = eia_info["message"]
        elif not session_info["is_open"]:
            directive = "STANDBY (MARKET CLOSED)"
            reason = session_info["guidance"]
        elif is_pre_ignition_long:
            directive = "⚡ PRE-IGNITION LAUNCHPAD (BUY CALL / LONG)"
            reason = f"Coiled at Launchpad: Price ({last_close:,.1f}) is only {dist_to_top_pct}% below Box Top ({bx_top:,.1f}) with 20/50 EMA momentum."
            entry_price = round(last_close, 2)
            risk_pts = round(max(last_close * 0.006, last_close - bx_mid), 2)
            stop_loss = round(entry_price - risk_pts, 2)
            target_1 = round(entry_price + (risk_pts * RISK_REWARD_RATIO), 2)
            target_2 = round(entry_price + (risk_pts * 2.5), 2)
            risk_per_lot = round(risk_pts * rupee_mult, 2)
            gain_per_lot = round((target_1 - entry_price) * rupee_mult, 2)
        elif is_pre_ignition_short:
            directive = "⚡ PRE-IGNITION LAUNCHPAD (BUY PUT / SHORT)"
            reason = f"Coiled at Breakdown Edge: Price ({last_close:,.1f}) is only {dist_to_bot_pct}% above Box Bottom ({bx_bottom:,.1f}) with downward momentum."
            entry_price = round(last_close, 2)
            risk_pts = round(max(last_close * 0.006, bx_mid - last_close), 2)
            stop_loss = round(entry_price + risk_pts, 2)
            target_1 = round(entry_price - (risk_pts * RISK_REWARD_RATIO), 2)
            target_2 = round(entry_price - (risk_pts * 2.5), 2)
            risk_per_lot = round(risk_pts * rupee_mult, 2)
            gain_per_lot = round((entry_price - target_1) * rupee_mult, 2)
        else:
            # Check Breakout Triggers
            if last_close > bx_top and bull_trend and vol_ratio >= 1.0:
                directive = "BUY LONG (BREAKOUT)"
                reason = f"Bullish breakout above {bx_top:,.2f} confirmed by 20 & 50 EMA and Volume ({vol_ratio:.1f}x)"
                entry_price = round(last_close, 2)
                
                # SL at box midline or bottom
                risk_pts = last_close - bx_mid
                max_risk_pts = last_close * MAX_STOP_LOSS_PCT
                if risk_pts <= 0 or risk_pts > max_risk_pts:
                    risk_pts = last_close * 0.008 # 0.8% default
                    
                stop_loss = round(entry_price - risk_pts, 2)
                target_1 = round(entry_price + (risk_pts * RISK_REWARD_RATIO), 2)
                target_2 = round(entry_price + (risk_pts * 2.0), 2)
                risk_per_lot = round(risk_pts * rupee_mult, 2)
                gain_per_lot = round((target_1 - entry_price) * rupee_mult, 2)
                
            elif last_close < bx_bottom and bear_trend and vol_ratio >= 1.0:
                directive = "SELL SHORT (BREAKDOWN)"
                reason = f"Bearish breakdown below {bx_bottom:,.2f} confirmed by 20 & 50 EMA and Volume ({vol_ratio:.1f}x)"
                entry_price = round(last_close, 2)
                
                risk_pts = bx_mid - last_close
                max_risk_pts = last_close * MAX_STOP_LOSS_PCT
                if risk_pts <= 0 or risk_pts > max_risk_pts:
                    risk_pts = last_close * 0.008
                    
                stop_loss = round(entry_price + risk_pts, 2)
                target_1 = round(entry_price - (risk_pts * RISK_REWARD_RATIO), 2)
                target_2 = round(entry_price - (risk_pts * 2.0), 2)
                risk_per_lot = round(risk_pts * rupee_mult, 2)
                gain_per_lot = round((entry_price - target_1) * rupee_mult, 2)
            else:
                if last_close > bx_top and not bull_trend:
                    reason = f"Breakout above {bx_top:,.2f} VETOED: Price below 50 EMA (Counter-Trend Trap)"
                elif last_close < bx_bottom and not bear_trend:
                    reason = f"Breakdown below {bx_bottom:,.2f} VETOED: Price above 50 EMA (Counter-Trend Trap)"
                elif vol_ratio < 1.0 and (last_close > bx_top or last_close < bx_bottom):
                    reason = f"Breakout lacks volume conviction (Vol: {vol_ratio:.2f}x avg)"
                else:
                    reason = f"Inside Range ({bx_bottom:,.2f} - {bx_top:,.2f}). Awaiting US session ignition."
                    
        return {
            "symbol": symbol,
            "display_name": spec.get("display_name", symbol),
            "lot_unit": lot_unit,
            "rupee_multiplier": rupee_mult,
            "typical_margin_inr": spec.get("typical_margin_inr", 0),
            "ltp": last_close,
            "ema20": round(last_ema20, 2),
            "ema50": round(last_ema50, 2),
            "box_top": round(bx_top, 2),
            "box_bottom": round(bx_bottom, 2),
            "box_mid": round(bx_mid, 2),
            "box_width_pct": round(box_width_pct, 2),
            "vol_ratio": round(vol_ratio, 2),
            "confluence_score": total_score,
            "score_breakdown": {
                "compression_pts": compression_pts,
                "trend_pts": trend_pts,
                "volume_pts": volume_pts,
                "session_pts": session_pts
            },
            "directive": directive,
            "reason": reason,
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "target_1": target_1,
            "target_2": target_2,
            "risk_per_lot_inr": risk_per_lot,
            "gain_per_lot_inr": gain_per_lot,
            "session_info": session_info,
            "eia_info": eia_info
        }

    def _empty_result(self, symbol: str, msg: str) -> Dict[str, Any]:
        spec = COMMODITY_SPECS.get(symbol, {})
        return {
            "symbol": symbol,
            "display_name": spec.get("display_name", symbol),
            "lot_unit": spec.get("lot_unit", "1 Lot"),
            "rupee_multiplier": spec.get("rupee_multiplier_per_point", 1.0),
            "typical_margin_inr": spec.get("typical_margin_inr", 0),
            "ltp": 0.0,
            "ema20": 0.0,
            "ema50": 0.0,
            "box_top": 0.0,
            "box_bottom": 0.0,
            "box_mid": 0.0,
            "box_width_pct": 0.0,
            "vol_ratio": 0.0,
            "confluence_score": 0,
            "score_breakdown": {"compression_pts": 0, "trend_pts": 0, "volume_pts": 0, "session_pts": 0},
            "directive": "HOLD CASH / STANDBY",
            "reason": msg,
            "entry_price": None,
            "stop_loss": None,
            "target_1": None,
            "target_2": None,
            "risk_per_lot_inr": 0.0,
            "gain_per_lot_inr": 0.0,
            "session_info": MCXSessionClock.get_session_info(),
            "eia_info": EIACalendarShield.get_shield_status(symbol)
        }

