"""
FinPlus+ Commodity Radar - Time & Logging Utilities
Strict ISO-8601 UTC for storage & logs; IST for MCX market operations.
"""

import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime, timezone
import zoneinfo

IST_TZ = zoneinfo.ZoneInfo("Asia/Kolkata")
UTC_TZ = timezone.utc

def get_utc_now() -> datetime:
    """Returns timezone-aware UTC datetime."""
    return datetime.now(UTC_TZ)

def get_ist_now() -> datetime:
    """Returns timezone-aware IST datetime."""
    return datetime.now(IST_TZ)

def get_utc_iso() -> str:
    """Returns ISO-8601 UTC string ending in 'Z'."""
    return get_utc_now().strftime("%Y-%m-%dT%H:%M:%SZ")

def get_ist_iso() -> str:
    """Returns ISO-8601 IST string with +05:30 offset."""
    return get_ist_now().strftime("%Y-%m-%dT%H:%M:%S+05:30")

def setup_logger(name: str, log_dir: str = "logs") -> logging.Logger:
    """
    Sets up enterprise structured logger with rotating file handler.
    Max 10MB per file, 5 backup copies.
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    if logger.handlers:
        return logger
        
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "commodity_radar.log")
    
    file_handler = RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=5, encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%SZ"
    )
    
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

