"""
FinPlus+ Official Indian Financial Markets Calendar
Manages official NSE/BSE and MCX trading holidays, session timings, and live market heartbeat checks.
"""

import datetime
from typing import Dict, Any, Tuple, Optional
import pytz

IST = pytz.timezone("Asia/Kolkata")

# MCX Holidays where Morning Session (09:00 - 17:00 IST) is closed
# Evening session opens at 17:00 IST
MCX_MORNING_CLOSED_HOLIDAYS = {
    "2026-03-03": "Holi",
    "2026-03-26": "Shri Ram Navami",
    "2026-03-31": "Shri Mahavir Jayanti",
    "2026-04-14": "Dr. Ambedkar Jayanti",
    "2026-05-01": "Maharashtra Day",
    "2026-05-28": "Bakri Id",
    "2026-06-26": "Muharram",
    "2026-09-14": "Ganesh Chaturthi",
    "2026-10-20": "Dussehra",
    "2026-11-10": "Diwali-Balipratipada",
    "2026-11-24": "Guru Nanak Jayanti"
}

# MCX Holidays where BOTH Morning & Evening Sessions are closed
MCX_FULL_DAY_HOLIDAYS = {
    "2026-01-26": "Republic Day",
    "2026-04-03": "Good Friday",
    "2026-08-15": "Independence Day",
    "2026-10-02": "Mahatma Gandhi Jayanti",
    "2026-12-25": "Christmas"
}


def get_current_ist_datetime() -> datetime.datetime:
    return datetime.datetime.now(tz=IST)


def is_mcx_market_open_ist() -> Tuple[bool, str]:
    """
    Checks if MCX Commodity market is currently open for order execution in India.
    Handles:
    1. Full-day MCX holidays
    2. Morning-closed holidays (09:00 - 17:00 IST closed, evening opens at 17:00 IST)
    3. Regular sessions (09:00 - 23:30 IST)
    """
    now_ist = get_current_ist_datetime()
    curr_date = now_ist.date()
    curr_time = now_ist.time()
    date_str = curr_date.strftime("%Y-%m-%d")

    # Weekend check
    if now_ist.weekday() >= 5:
        return False, "Weekend (Saturday/Sunday) - MCX Closed"

    # Full Day MCX Holiday
    if date_str in MCX_FULL_DAY_HOLIDAYS:
        return False, f"MCX Full-Day Holiday ({MCX_FULL_DAY_HOLIDAYS[date_str]})"

    # Morning session closed holiday (e.g. Diwali Balipratipada)
    if date_str in MCX_MORNING_CLOSED_HOLIDAYS:
        hol_name = MCX_MORNING_CLOSED_HOLIDAYS[date_str]
        if curr_time < datetime.time(17, 0):
            return False, f"MCX Morning Closed ({hol_name}) - Evening Session opens at 05:00 PM (17:00 IST)"
        elif curr_time > datetime.time(23, 30):
            return False, f"MCX Evening Session Closed (23:30 IST)"
        return True, f"MCX Evening Session Active ({hol_name})"

    # Regular session: 09:00 to 23:30 IST
    if not (datetime.time(9, 0) <= curr_time <= datetime.time(23, 30)):
        return False, f"MCX Off-Hours (Current: {curr_time.strftime('%H:%M:%S')}, Hours: 09:00 - 23:30 IST)"

    return True, "MCX Market Open"
