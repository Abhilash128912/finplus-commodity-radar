import os
import pytest
from unittest.mock import patch, MagicMock
from src.notifications.ntfy_dispatcher import CommodityNTFYDispatcher

def test_ntfy_suppression_when_not_on_render(monkeypatch, caplog):
    """
    Verifies that all NTFY sends in finplus_commodity_radar are blocked when RENDER is unset.
    - Local runs return False and execute zero network requests.
    - Logs 'NTFY suppressed (not on Render)' at most once per hour.
    """
    import logging
    monkeypatch.delenv("FINPLUS_ENV", raising=False)
    monkeypatch.delenv("FINPLUS_ENVIRONMENT", raising=False)
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.delenv("RENDER_SERVICE_ID", raising=False)

    dispatcher = CommodityNTFYDispatcher()

    with patch("requests.post") as mock_post, caplog.at_level(logging.INFO):
        # 1. First send: suppressed and logged
        res1 = dispatcher._send_to_ntfy("Finplus-Commodity", "Body 1", {"Title": "Test Alert 1"})
        assert res1 is False
        assert mock_post.call_count == 0
        assert "NTFY suppressed (not on Render)" in caplog.text

        # 2. Second send within 1 hour: suppressed but NOT logged again
        caplog.clear()
        res2 = dispatcher._send_to_ntfy("Finplus-Commodity", "Body 2", {"Title": "Test Alert 2"})
        assert res2 is False
        assert mock_post.call_count == 0
        assert "NTFY suppressed (not on Render)" not in caplog.text

def test_ntfy_allowed_when_on_render(monkeypatch):
    """Verifies that NTFY dispatches normally when RENDER is set."""
    monkeypatch.delenv("FINPLUS_ENV", raising=False)
    monkeypatch.delenv("FINPLUS_ENVIRONMENT", raising=False)
    monkeypatch.setenv("RENDER", "true")
    dispatcher = CommodityNTFYDispatcher()

    mock_resp = MagicMock(status_code=200)
    with patch("requests.post", return_value=mock_resp) as mock_post:
        res = dispatcher._send_to_ntfy("Finplus-Commodity", "Body Cloud", {"Title": "Test Cloud Alert"})
        assert res is True
        assert mock_post.call_count == 1

