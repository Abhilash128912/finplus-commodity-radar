# 🛢️ FinPlus+ MCX Commodity Radar (APP-03)
**Application ID:** APP-03  
**Port:** 8002  
**Target Derivatives:** Natural Gas Mini (`NATGASMINI`), Crude Oil Mini (`CRUDEOILM`), Gold Petal (`GOLDPETAL`)  
**Established:** 2026-11-08  
**Compliance Standard:** ISO-8601 UTC Internal • IST Market Operations • Zero Fabricated Data  

---

## 📌 Executive Summary
FinPlus+ MCX Commodity Radar is a quantitative early-ignition and risk-budgeting cockpit engineered specifically for low-to-moderate capital derivatives trading.

It monitors the 14-hour MCX commodity trading window (09:00 AM – 11:30 PM IST), isolating the **US Session Prime Window (18:00 – 21:30 IST)** where NYMEX and COMEX institutional volume creates genuine expansion breakouts.

---

## 📊 Core Quantitative Strategy
1. **15-Minute LuxAlgo Range Compression:**
   - Detects 15-period volatility contraction against ATR 200 (< 2.5% band).
2. **20 & 50 EMA Trend Gate (Filter A):**
   - Long Breakout: `Price > 20 EMA` AND `Price > 50 EMA`.
   - Short Breakdown: `Price < 20 EMA` AND `Price < 50 EMA`.
   - Blocks counter-trend trap breakouts.
3. **Volume Conviction Sentry:**
   - Requires Volume > 1.2x 20-period Average Volume.
4. **EIA News Shield:**
   - **Wednesdays 20:00 IST:** Freezes Crude Oil entries from 19:55 to 20:05 IST to protect against EIA petroleum inventory spread blowouts.
   - **Thursdays 20:00 IST:** Freezes Natural Gas entries from 19:55 to 20:05 IST to protect against EIA storage report spikes.

---

## 🪙 Tradable Contracts Matrix

| Symbol | Benchmark | Lot Unit | Rupee Multiplier | Margin (MIS) | R:R Target |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`CRUDEOILM`** | WTI Crude Oil | 10 Barrels | **₹10 / pt** | ~₹22,000 | 1:1.5 |
| **`NATGASMINI`** | Henry Hub Gas | 250 mmBtu | **₹250 / pt** | ~₹28,000 | 1:1.5 |
| **`GOLDPETAL`** | COMEX Gold 999 | 1 Gram | **₹1 / pt** | ~₹1,000 | 1:1.5 |

---

## 🚀 Running the Application
```bash
# Terminal Runner
cd D:\AI_APPS\finplus_commodity_radar
python -m uvicorn src.api.server:app --host 127.0.0.1 --port 8002
```
Or launch via `D:\AI_APPS\START_ALL_FINPLUS_SERVERS.bat`.

