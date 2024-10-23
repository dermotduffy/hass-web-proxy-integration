"""Tests for the HASS Web Proxy integration."""

from types import MappingProxyType
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
)

from custom_components.hass_web_proxy.const import DOMAIN

TEST_CONFIG_ENTRY_ID = "74565bd414754616000674c87bdc876d"
TEST_TITLE = "Home Assistant Web Proxy"


def create_mock_hass_web_proxy_config_entry(
    hass: HomeAssistant,
    options: MappingProxyType[str, Any] | None = None,
    entry_id: str | None = TEST_CONFIG_ENTRY_ID,
    title: str | None = TEST_TITLE,
) -> ConfigEntry:
    """Add a test config entry."""
    config_entry: MockConfigEntry = MockConfigEntry(
        entry_id=entry_id,
        domain=DOMAIN,
        data={},
        title=title,
        options=options or {},
    )
    config_entry.add_to_hass(hass)
    return config_entry


async def setup_mock_hass_web_proxy_config_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry | None = None,
) -> ConfigEntry:
    """Add a mock Frigate config entry to hass."""
    config_entry = config_entry or create_mock_hass_web_proxy_config_entry(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    return config_entry
