"""Constants for hass_proxy."""

from logging import Logger, getLogger
from typing import Final

from homeassistant.util.ssl import SSLCipherList

DOMAIN: Final = "hass_proxy"

LOGGER: Logger = getLogger(__package__)

CONF_SSL_VERIFICATION: Final = "ssl_verification"
CONF_SSL_CIPHERS: Final = "ssl_ciphers"
CONF_SSL_CIPHER_INSECURE: Final = SSLCipherList.INSECURE
CONF_SSL_CIPHER_MODERN: Final = SSLCipherList.MODERN
CONF_SSL_CIPHER_INTERMEDIATE: Final = SSLCipherList.INTERMEDIATE
CONF_SSL_CIPHER_PYTHON_DEFAULT: Final = SSLCipherList.PYTHON_DEFAULT

CONF_DYNAMIC_URLS: Final = "dynamic_urls"
CONF_URL_PATTERNS: Final = "url_patterns"

DEFAULT_OPTIONS: dict[str, str | bool | list[str]] = {
    CONF_SSL_VERIFICATION: True,
    CONF_DYNAMIC_URLS: True,
    CONF_SSL_CIPHERS: CONF_SSL_CIPHER_PYTHON_DEFAULT,
}
