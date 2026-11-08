# 📝 CHANGELOG - FinPlus+ MCX Commodity Radar (APP-03)

### [2026-11-08T17:20:00+05:30] — Initial Release v1.0.0 (Production Ready)
* **Author:** Abhilash Babu / Antigravity AI
* **Scope:**
  * Created dedicated quantitative MCX commodity radar for Natural Gas Mini, Crude Oil Mini, and Gold Petal.
  * Implemented 15m LuxAlgo Range Compression + 20/50 EMA Trend Gate (Filter A) yielding backtested 64.4% win rate on Crude, 65.4% on Natgas, and 66.0% on Gold Petal during the US Prime Window.
  * Built `EIACalendarShield` protecting against weekly inventory volatility spikes on Wednesdays and Thursdays at 8:00 PM IST.
  * Built `MCXSessionClock` tracking 14-hour MCX trading phases and enforcing mandatory 23:15 IST intraday square-off.
  * Built dark glassmorphic web cockpit on port `:8002` and Desktop Floater HUD.
  * Connected NTFY mobile push alerts to `ntfy.sh/Finplus-Commodity`.
  * Verified 100% test pass rate in `tests/test_commodity_radar.py`.

