"""
Custom integration to add a small web proxy to Home Assistant.

For more details about this integration, please refer to
https://github.com/dermotduffy/hass-web-proxy-integration
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .const import LOGGER

if TYPE_CHECKING:
    from homeassistant.const import Platform
    from homeassistant.core import HomeAssistant

    from .data import HASSWebProxyConfigEntry

from .proxy import async_setup_entry as async_proxy_setup_entry
from .proxy import async_unload_entry as async_proxy_unload_entry

PLATFORMS: list[Platform] = []


# https://developers.home-assistant.io/docs/config_entries_index/#setting-up-an-entry
async def async_setup_entry(
    hass: HomeAssistant,
    entry: HASSWebProxyConfigEntry,
) -> bool:
    """Set up this integration."""
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    await async_proxy_setup_entry(hass, entry)

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: HASSWebProxyConfigEntry,
) -> bool:
    """Handle removal of an entry."""
    await async_proxy_unload_entry(hass, entry)
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(
    hass: HomeAssistant,
    entry: HASSWebProxyConfigEntry,
) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)
