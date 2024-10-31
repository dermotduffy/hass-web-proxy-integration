"""Custom types for HASS Web Proxy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.loader import Integration


@dataclass
class DynamicProxiedURL:
    """A proxied URL."""

    url_pattern: str
    ssl_verification: bool
    ssl_ciphers: str
    open_limit: int
    expiration: int
    allow_unauthenticated: bool


type HASSWebProxyConfigEntry = ConfigEntry[HASSWebProxyData]


@dataclass
class HASSWebProxyData:
    """Data for the HASS Web Proxy integration."""

    integration: Integration
    dynamic_proxied_urls: dict[str, DynamicProxiedURL]
