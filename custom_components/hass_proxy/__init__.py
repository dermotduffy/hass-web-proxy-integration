"""
Custom integration to add a tiny proxy to Home Assistant.

For more details about this integration, please refer to
https://github.com/dermotduffy/hass-proxy
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .const import LOGGER

if TYPE_CHECKING:
    from homeassistant.const import Platform
    from homeassistant.core import HomeAssistant

    from .data import HASSProxyData

PLATFORMS: list[Platform] = []


# https://developers.home-assistant.io/docs/config_entries_index/#setting-up-an-entry
async def async_setup_entry(
    hass: HomeAssistant,
    entry: HASSProxyData,
) -> bool:
    """Set up this integration."""
    LOGGER.info("HASSPROXY Setting up entry %s", entry.entry_id)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: HASSProxyData,
) -> bool:
    """Handle removal of an entry."""

    LOGGER.info("HASSPROXY Unloading entry %s", entry.entry_id)
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(
    hass: HomeAssistant,
    entry: HASSProxyData,
) -> None:
    """Reload config entry."""
    LOGGER.info("HASSPROXY Reloading entry %s", entry.entry_id)

    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
