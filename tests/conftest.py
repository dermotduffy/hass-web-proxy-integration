"""Global fixtures for HASS Web Proxy integration."""

from typing import Any

import pytest

pytest_plugins = [
    "pytest_homeassistant_custom_component",
    "hass_web_proxy_lib.tests.utils",
]

@pytest.fixture(autouse=True)
def hass_web_proxy_integration_fixture(
    socket_enabled: Any,
    skip_notifications: Any,
    enable_custom_integrations: Any,
    hass: Any,
) -> None:
    """Automatically use an ordered combination of fixtures."""
