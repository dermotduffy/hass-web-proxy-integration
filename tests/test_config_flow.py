"""Test the HASS Web Proxy config flow."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

from homeassistant import config_entries, data_entry_flow

from custom_components.hass_web_proxy.const import (
    CONF_DYNAMIC_URLS,
    CONF_SSL_CIPHERS,
    CONF_SSL_VERIFICATION,
    CONF_URL_PATTERNS,
    DOMAIN,
)

from . import (
    create_mock_hass_web_proxy_config_entry,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


async def test_user_success(hass: HomeAssistant) -> None:
    """Test successful user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "create_entry"
    assert result["title"] == "Home Assistant Web Proxy"


async def test_user_multiple_forbidden(hass: HomeAssistant) -> None:
    """Test multiple instances are forbidden."""
    create_mock_hass_web_proxy_config_entry(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_options(hass: HomeAssistant) -> None:
    """Test the options flow."""
    config_entry = create_mock_hass_web_proxy_config_entry(hass)

    with patch(
        "custom_components.hass_web_proxy.async_setup_entry",
        return_value=True,
    ):
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_URL_PATTERNS: ["http://localhost"],
                CONF_SSL_VERIFICATION: True,
                CONF_SSL_CIPHERS: "default",
                CONF_DYNAMIC_URLS: True,
            },
        )
        await hass.async_block_till_done()
        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["data"][CONF_URL_PATTERNS] == ["http://localhost"]
        assert result["data"][CONF_SSL_VERIFICATION]
        assert result["data"][CONF_SSL_CIPHERS] == "default"
        assert result["data"][CONF_SSL_CIPHERS]
