"""Constants for hass_proxy."""

from logging import Logger, getLogger
from typing import Final, Literal

DOMAIN: Final = "hass_proxy"

LOGGER: Logger = getLogger(__package__)

CONF_SSL_VERIFICATION: Final = "ssl_verification"
CONF_SSL_CIPHERS: Final = "ssl_ciphers"

CONF_SSL_CIPHERS_INSECURE: Final = "insecure"
CONF_SSL_CIPHERS_MODERN: Final = "modern"
CONF_SSL_CIPHERS_INTERMEDIATE: Final = "intermediate"
CONF_SSL_CIPHERS_DEFAULT: Final = "default"

type HASSProxySSLCiphers = Literal["insecure", "modern", "intermediate", "default"]

CONF_DYNAMIC_URLS: Final = "dynamic_urls"
CONF_URL_PATTERNS: Final = "url_patterns"

SERVICE_CREATE_PROXIED_URL: Final = "create_proxied_url"
SERVICE_DELETE_PROXIED_URL: Final = "delete_proxied_url"

DEFAULT_OPTIONS: dict[str, str | bool | list[str]] = {
    CONF_SSL_VERIFICATION: True,
    CONF_DYNAMIC_URLS: True,
    CONF_SSL_CIPHERS: CONF_SSL_CIPHERS_DEFAULT,
}
