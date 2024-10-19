"""HASS Proxy proxy."""

from __future__ import annotations

import urllib
from typing import TYPE_CHECKING, Any

import urlmatch
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util.ssl import (
    client_context,
    client_context_no_verify,
)

from custom_components.hass_proxy.const import DOMAIN
from custom_components.hass_proxy.proxy_lib import (
    HASSProxyNotFoundRequestError,
    ProxiedURL,
    ProxyView,
)

from .const import CONF_SSL_CIPHERS, CONF_SSL_VERIFICATION

if TYPE_CHECKING:
    import ssl
    from types import MappingProxyType

    import aiohttp
    from aiohttp import web
    from homeassistant.core import HomeAssistant


async def async_setup(hass: HomeAssistant) -> None:
    """Set up the views."""
    session = async_get_clientsession(hass)
    hass.http.register_view(V0ProxyView(hass, session))


class HAProxyView(ProxyView):
    """A proxy view for HomeAssistant."""

    def __init__(self, hass: HomeAssistant, websession: aiohttp.ClientSession) -> None:
        """Initialize the HASS Proxy view."""
        self._hass = hass
        super().__init__(websession)

    def _get_options(self) -> MappingProxyType[str, Any]:
        """Get a ConfigEntry options for a given request."""
        return self._hass.config_entries.async_entries(DOMAIN)[0].options

    def _get_url_to_proxy(self, request: web.Request) -> str:
        """Get the URL to proxy."""
        if "url" not in request.query:
            raise HASSProxyNotFoundRequestError

        url_to_proxy = urllib.parse.unquote(request.query["url"])
        for url_pattern in self._get_options().get("url_patterns", []):
            if urlmatch.urlmatch(url_pattern, url_to_proxy, path_required=False):
                break
        else:
            raise HASSProxyNotFoundRequestError

        return url_to_proxy

    def _get_ssl_context(self) -> ssl.SSLContext:
        """Get an SSL context."""
        options = self._get_options()

        if not options.get(CONF_SSL_VERIFICATION, True):
            return client_context_no_verify(options.get(CONF_SSL_CIPHERS))
        return client_context(options.get(CONF_SSL_CIPHERS))


class V0ProxyView(HAProxyView):
    """A v0 proxy endpoint."""

    url = "/api/hass_proxy/v0/"
    name = "api:hass_proxy:v0"

    def _get_proxied_url(self, request: web.Request, **_kwargs: Any) -> str:
        """Create path."""
        return ProxiedURL(self._get_url_to_proxy(request), self._get_ssl_context())
