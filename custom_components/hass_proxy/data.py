"""Custom types for hass_proxy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.loader import Integration


type HASSProxyConfigEntry = ConfigEntry[HASSProxyData]


@dataclass
class HASSProxyData:
    """Data for the HASS Proxy integration."""

    integration: Integration
