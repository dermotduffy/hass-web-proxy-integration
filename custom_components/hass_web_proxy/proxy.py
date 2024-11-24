"""HASS Web Proxy proxy."""

from __future__ import annotations

import time
import urllib
import uuid
from typing import TYPE_CHECKING, Any

import urlmatch
import voluptuous as vol
from hass_web_proxy_lib import (
    LOGGER,
    HASSWebProxyLibNotFoundRequestError,
    ProxiedURL,
    ProxyView,
)
from homeassistant.core import ServiceResponse, SupportsResponse, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.loader import async_get_loaded_integration
from homeassistant.util.ssl import (
    SSLCipherList,
    client_context,
    client_context_no_verify,
)

from .const import (
    CONF_ALLOW_UNAUTHENTICATED,
    CONF_DYNAMIC_URLS,
    CONF_OPEN_LIMIT,
    CONF_SSL_CIPHERS,
    CONF_SSL_CIPHERS_DEFAULT,
    CONF_SSL_CIPHERS_INSECURE,
    CONF_SSL_CIPHERS_INTERMEDIATE,
    CONF_SSL_CIPHERS_MODERN,
    CONF_SSL_VERIFICATION,
    CONF_TTL,
    CONF_URL_ID,
    CONF_URL_PATTERN,
    DOMAIN,
    SERVICE_CREATE_PROXIED_URL,
    SERVICE_DELETE_PROXIED_URL,
)
from .data import (
    DynamicProxiedURL,
    HASSWebProxyConfigEntry,
    HASSWebProxyData,
)

if TYPE_CHECKING:
    import ssl
    from types import MappingProxyType

    import aiohttp
    from aiohttp import web
    from homeassistant.core import HomeAssistant, ServiceCall


CREATE_PROXIED_URL_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL_PATTERN): cv.string,
        vol.Optional(CONF_URL_ID): cv.string,
        vol.Optional(CONF_SSL_VERIFICATION, default=True): cv.boolean,
        vol.Optional(CONF_SSL_CIPHERS, default=CONF_SSL_CIPHERS_DEFAULT): vol.Any(
            None,
            CONF_SSL_CIPHERS_INSECURE,
            CONF_SSL_CIPHERS_MODERN,
            CONF_SSL_CIPHERS_INTERMEDIATE,
            CONF_SSL_CIPHERS_DEFAULT,
        ),
        vol.Optional(CONF_OPEN_LIMIT, default=1): cv.positive_int,
        vol.Optional(CONF_TTL, default=60): cv.positive_int,
        vol.Optional(CONF_ALLOW_UNAUTHENTICATED, default=False): cv.boolean,
    },
    required=True,
)

DELETE_PROXIED_URL_SCHEMA = vol.Schema(
    {
        vol.Required("url_id"): cv.string,
    },
    required=True,
)


@callback
async def async_setup_entry(
    hass: HomeAssistant, entry: HASSWebProxyConfigEntry
) -> None:
    """Set up the HASS web proxy entry."""
    session = async_get_clientsession(hass)
    hass.http.register_view(V0ProxyView(hass, session))

    entry.runtime_data = HASSWebProxyData(
        integration=async_get_loaded_integration(hass, entry.domain),
        dynamic_proxied_urls={},
    )

    def create_proxied_url(call: ServiceCall) -> ServiceResponse:
        """Create a proxied URL."""
        url_id = call.data.get("url_id") or str(uuid.uuid4())
        ttl = call.data["ttl"]

        entry.runtime_data.dynamic_proxied_urls[url_id] = DynamicProxiedURL(
            url_pattern=call.data["url_pattern"],
            ssl_verification=call.data["ssl_verification"],
            ssl_ciphers=call.data["ssl_ciphers"],
            open_limit=call.data["open_limit"],
            expiration=time.time() + ttl if ttl else 0,
            allow_unauthenticated=call.data["allow_unauthenticated"],
        )

        LOGGER.debug(f"Created dynamically proxied URL '{url_id}': {call.data}")

        return {"url_id": url_id}

    def delete_proxied_url(call: ServiceCall) -> None:
        """Delete a proxied URL."""
        url_id = call.data["url_id"]
        dynamic_proxied_urls = entry.runtime_data.dynamic_proxied_urls

        if url_id not in dynamic_proxied_urls:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="url_id_not_found",
                translation_placeholders={"url_id": url_id},
            )
        del entry.runtime_data.dynamic_proxied_urls[url_id]

        LOGGER.debug(f"Deleted dynamically proxied URL '{url_id}'")

    if entry.options.get(CONF_DYNAMIC_URLS):
        hass.services.async_register(
            DOMAIN,
            SERVICE_CREATE_PROXIED_URL,
            create_proxied_url,
            CREATE_PROXIED_URL_SCHEMA,
            supports_response=SupportsResponse.OPTIONAL,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_DELETE_PROXIED_URL,
            delete_proxied_url,
            DELETE_PROXIED_URL_SCHEMA,
        )


@callback
async def async_unload_entry(
    hass: HomeAssistant, entry: HASSWebProxyConfigEntry
) -> None:
    """Unload the proxy entry."""
    if entry.options.get(CONF_DYNAMIC_URLS):
        hass.services.async_remove(DOMAIN, SERVICE_CREATE_PROXIED_URL)
        hass.services.async_remove(DOMAIN, SERVICE_DELETE_PROXIED_URL)


class HAProxyView(ProxyView):
    """A proxy view for HomeAssistant."""

    def __init__(self, hass: HomeAssistant, websession: aiohttp.ClientSession) -> None:
        """Initialize the HASS Web Proxy view."""
        self._hass = hass
        super().__init__(websession)

    def _get_config_entry(self) -> HASSWebProxyConfigEntry:
        """Get the config entry."""
        return self._hass.config_entries.async_entries(DOMAIN)[0]

    def get_dynamic_proxied_urls(self) -> dict[str, DynamicProxiedURL]:
        """Get the dynamic proxied URLs."""
        return self._get_config_entry().runtime_data.dynamic_proxied_urls

    def _get_options(self) -> MappingProxyType[str, Any]:
        """Get a ConfigEntry options for a given request."""
        return self._get_config_entry().options

    def _cleanup_expired_urls(self) -> None:
        """Cleanup expired URLs."""
        proxied_urls = self.get_dynamic_proxied_urls()
        for url_id, proxied_url in list(proxied_urls.items()):
            if proxied_url.expiration and proxied_url.expiration < time.time():
                del proxied_urls[url_id]

    def _get_proxied_url(self, request: web.Request, **_kwargs: Any) -> ProxiedURL:
        """Get the URL to proxy."""
        LOGGER.debug(
            f"Received proxy request '{request.query}',"
            f" dynamic proxied URLs: {self.get_dynamic_proxied_urls()},"
            f" static options: {self._get_options()}."
        )

        if "url" not in request.query:
            raise HASSWebProxyLibNotFoundRequestError

        options = self._get_options()
        url_to_proxy = urllib.parse.unquote(request.query["url"])

        self._cleanup_expired_urls()

        proxied_urls = self.get_dynamic_proxied_urls()
        for [url_id, proxied_url] in proxied_urls.items():
            if urlmatch.urlmatch(
                proxied_url.url_pattern,
                url_to_proxy,
                path_required=False,
            ):
                if proxied_url.open_limit:
                    proxied_url.open_limit -= 1
                    if proxied_url.open_limit == 0:
                        del proxied_urls[url_id]

                return ProxiedURL(
                    url=url_to_proxy,
                    allow_unauthenticated=proxied_url.allow_unauthenticated,
                    ssl_context=self._get_ssl_context(proxied_url.ssl_ciphers)
                    if proxied_url.ssl_verification
                    else self._get_ssl_context_no_verify(proxied_url.ssl_ciphers),
                )

        for url_pattern in self._get_options().get("url_patterns", []):
            if urlmatch.urlmatch(url_pattern, url_to_proxy, path_required=False):
                ssl_cipher = str(options.get(CONF_SSL_CIPHERS))
                ssl_verification = options.get(CONF_SSL_VERIFICATION, True)

                return ProxiedURL(
                    url=url_to_proxy,
                    ssl_context=self._get_ssl_context(ssl_cipher)
                    if ssl_verification
                    else self._get_ssl_context_no_verify(ssl_cipher),
                )

        raise HASSWebProxyLibNotFoundRequestError

    def _get_ssl_context_no_verify(self, ssl_cipher: str) -> ssl.SSLContext:
        """Get an SSL context."""
        return client_context_no_verify(
            self._proxy_ssl_cipher_to_ha_ssl_cipher(ssl_cipher)
        )

    def _get_ssl_context(self, ssl_ciphers: str) -> ssl.SSLContext:
        """Get an SSL context."""
        return client_context(self._proxy_ssl_cipher_to_ha_ssl_cipher(ssl_ciphers))

    def _proxy_ssl_cipher_to_ha_ssl_cipher(self, ssl_ciphers: str) -> SSLCipherList:
        """Convert a proxy SSL cipher to a HA SSL cipher."""
        if ssl_ciphers == CONF_SSL_CIPHERS_INSECURE:
            return SSLCipherList.INSECURE
        if ssl_ciphers == CONF_SSL_CIPHERS_MODERN:
            return SSLCipherList.MODERN
        if ssl_ciphers == CONF_SSL_CIPHERS_INTERMEDIATE:
            return SSLCipherList.INTERMEDIATE
        return SSLCipherList.PYTHON_DEFAULT


class V0ProxyView(HAProxyView):
    """A v0 proxy endpoint."""

    url = "/api/hass_web_proxy/v0/"
    name = "api:hass_web_proxy:v0"
