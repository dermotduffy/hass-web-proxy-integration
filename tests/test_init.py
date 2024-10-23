"""Test the HASS Web proxy __init__.py file."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntryState

from custom_components.hass_web_proxy.const import DOMAIN
from tests import setup_mock_hass_web_proxy_config_entry

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


async def test_entry_setup(hass: HomeAssistant) -> None:
    """Test setting up a config entry."""
    config_entry = await setup_mock_hass_web_proxy_config_entry(hass)

    config_entries = hass.config_entries.async_entries(DOMAIN)
    assert len(config_entries) == 1
    assert config_entries[0] is config_entry
    assert config_entry.state == ConfigEntryState.LOADED


async def test_entry_unload(hass: HomeAssistant) -> None:
    """Test unloading a config entry."""
    config_entry = await setup_mock_hass_web_proxy_config_entry(hass)
    assert config_entry.state == ConfigEntryState.LOADED

    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state == ConfigEntryState.NOT_LOADED


async def test_entry_update(hass: HomeAssistant) -> None:
    """Test updating a config entry."""
    config_entry = await setup_mock_hass_web_proxy_config_entry(hass)

    assert hass.config_entries.async_update_entry(entry=config_entry, title="new title")
    await hass.async_block_till_done()

    # Entry will have been reloaded, and config will be re-fetched.
    assert config_entry.title == "new title"
