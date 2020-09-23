""" Unit tests for the fireweather noon forecats bot (Bender) """
import os
import logging
import requests
import pytest
import app
from app.tests.conftest import mock_requests_session
from app.fireweather_bot import noon_forecasts

logger = logging.getLogger(__name__)


def test_noon_forecasts_bot(mock_requests_session):
    """ Very simple (not very good) test that checks that the bot exits with a success code. """
    with pytest.raises(SystemExit) as excinfo:
        noon_forecasts.main()
    assert excinfo.value.code == 0