"""Test the proxy lib."""

from __future__ import annotations

import datetime
import urllib
from http import HTTPStatus
from typing import TYPE_CHECKING, Any

import pytest
from homeassistant.exceptions import ServiceValidationError

from custom_components.hass_proxy.const import (
    CONF_DYNAMIC_URLS,
    CONF_OPEN_LIMIT,
    CONF_SSL_CIPHERS,
    CONF_SSL_VERIFICATION,
    CONF_TTL,
    CONF_URL_ID,
    CONF_URL_PATTERN,
    CONF_URL_PATTERNS,
    DOMAIN,
    SERVICE_CREATE_PROXIED_URL,
    SERVICE_DELETE_PROXIED_URL,
)
from custom_components.hass_proxy.proxy import (
    async_setup_entry as async_proxy_setup_entry,
)
from tests import (
    create_mock_hass_proxy_config_entry,
    setup_mock_hass_proxy_config_entry,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

TEST_OPTIONS = {
    CONF_DYNAMIC_URLS: True,
    CONF_SSL_CIPHERS: "default",
    CONF_SSL_VERIFICATION: True,
    CONF_URL_PATTERNS: [],
}

TEST_SERVICE_CALL_PARAMS = {
    CONF_OPEN_LIMIT: 0,
    CONF_SSL_CIPHERS: "default",
    CONF_SSL_VERIFICATION: True,
    CONF_TTL: 0,
}


async def test_proxy_view_ok(
    hass: HomeAssistant,
    local_server: Any,
    hass_client: Any,
) -> None:
    """Test that a valid URL causes OK."""
    config_entry = create_mock_hass_proxy_config_entry(
        hass,
        {
            **TEST_OPTIONS,
            CONF_URL_PATTERNS: [f"{local_server}ok"],
        },
    )
    await setup_mock_hass_proxy_config_entry(hass, config_entry)
    await async_proxy_setup_entry(hass, config_entry)

    authenticated_hass_client = await hass_client()
    resp = await authenticated_hass_client.get(
        f"/api/hass_proxy/v0/?url={urllib.parse.quote_plus(f"{local_server}ok")}"
    )
    assert resp.status == HTTPStatus.OK


@pytest.mark.usefixtures("local_server")
async def test_proxy_view_without_url_parameter(
    hass: HomeAssistant,
    hass_client: Any,
) -> None:
    """Verify proxying without a url querystring parameter."""
    config_entry = create_mock_hass_proxy_config_entry(hass)

    await setup_mock_hass_proxy_config_entry(hass, config_entry)
    await async_proxy_setup_entry(hass, config_entry)

    authenticated_hass_client = await hass_client()
    resp = await authenticated_hass_client.get("/api/hass_proxy/v0/")
    assert resp.status == HTTPStatus.NOT_FOUND


async def test_proxy_view_no_matching_url(
    hass: HomeAssistant,
    local_server: Any,
    hass_client: Any,
) -> None:
    """Verify proxying without a matching URL."""
    config_entry = create_mock_hass_proxy_config_entry(
        hass,
        {
            **TEST_OPTIONS,
            CONF_URL_PATTERNS: [],
        },
    )
    await setup_mock_hass_proxy_config_entry(hass, config_entry)
    await async_proxy_setup_entry(hass, config_entry)

    authenticated_hass_client = await hass_client()
    resp = await authenticated_hass_client.get(
        f"/api/hass_proxy/v0/?url={urllib.parse.quote_plus(f"{local_server}ok")}"
    )
    assert resp.status == HTTPStatus.NOT_FOUND


async def test_proxy_view_ssl_insecure_no_verify(
    hass: HomeAssistant,
    local_server: Any,
    hass_client: Any,
) -> None:
    """Verify proxying with insecure SSL settings."""
    config_entry = create_mock_hass_proxy_config_entry(
        hass,
        {
            **TEST_OPTIONS,
            CONF_URL_PATTERNS: [f"{local_server}ok"],
            CONF_SSL_CIPHERS: "insecure",
            CONF_SSL_VERIFICATION: False,
        },
    )
    await setup_mock_hass_proxy_config_entry(hass, config_entry)
    await async_proxy_setup_entry(hass, config_entry)

    authenticated_hass_client = await hass_client()
    resp = await authenticated_hass_client.get(
        f"/api/hass_proxy/v0/?url={urllib.parse.quote_plus(f"{local_server}ok")}"
    )
    assert resp.status == HTTPStatus.OK


async def test_proxy_view_dynamic_url_ok(
    hass: HomeAssistant,
    local_server: Any,
    hass_client: Any,
) -> None:
    """Test that a valid dynamic URL causes OK."""
    config_entry = create_mock_hass_proxy_config_entry(hass, TEST_OPTIONS)

    await setup_mock_hass_proxy_config_entry(hass, config_entry)
    await async_proxy_setup_entry(hass, config_entry)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_CREATE_PROXIED_URL,
        {
            **TEST_SERVICE_CALL_PARAMS,
            CONF_URL_PATTERN: f"{local_server}ok",
        },
        blocking=True,
    )

    authenticated_hass_client = await hass_client()
    resp = await authenticated_hass_client.get(
        f"/api/hass_proxy/v0/?url={urllib.parse.quote_plus(f"{local_server}ok")}"
    )
    assert resp.status == HTTPStatus.OK


async def test_proxy_view_dynamic_url_delete(
    hass: HomeAssistant,
    local_server: Any,
    hass_client: Any,
) -> None:
    """Test that a dynamic URL can be deleted."""
    config_entry = create_mock_hass_proxy_config_entry(hass, TEST_OPTIONS)

    await setup_mock_hass_proxy_config_entry(hass, config_entry)
    await async_proxy_setup_entry(hass, config_entry)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_CREATE_PROXIED_URL,
        {
            **TEST_SERVICE_CALL_PARAMS,
            CONF_URL_ID: "id",
            CONF_URL_PATTERN: f"{local_server}ok",
        },
        blocking=True,
    )
    await hass.services.async_call(
        DOMAIN,
        SERVICE_DELETE_PROXIED_URL,
        {
            CONF_URL_ID: "id",
        },
        blocking=True,
    )

    authenticated_hass_client = await hass_client()
    resp = await authenticated_hass_client.get(
        f"/api/hass_proxy/v0/?url={urllib.parse.quote_plus(f"{local_server}ok")}"
    )
    assert resp.status == HTTPStatus.NOT_FOUND


async def test_proxy_view_dynamic_url_delete_not_existant(hass: HomeAssistant) -> None:
    """Test that an invalid dynamic URL cannot be deleted."""
    config_entry = create_mock_hass_proxy_config_entry(hass, TEST_OPTIONS)

    await setup_mock_hass_proxy_config_entry(hass, config_entry)
    await async_proxy_setup_entry(hass, config_entry)

    with pytest.raises(ServiceValidationError) as service_validation_error:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_DELETE_PROXIED_URL,
            {
                CONF_URL_ID: "not-existant-id",
            },
            blocking=True,
        )

    assert str(service_validation_error.value) == 'URL ID "not-existant-id" not found'


async def test_proxy_view_dynamic_url_open_limit(
    hass: HomeAssistant,
    local_server: Any,
    hass_client: Any,
) -> None:
    """Test that a dynamic URL respects open limits."""
    config_entry = create_mock_hass_proxy_config_entry(hass, TEST_OPTIONS)

    await setup_mock_hass_proxy_config_entry(hass, config_entry)
    await async_proxy_setup_entry(hass, config_entry)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_CREATE_PROXIED_URL,
        {
            **TEST_SERVICE_CALL_PARAMS,
            CONF_OPEN_LIMIT: 1,
            CONF_URL_PATTERN: f"{local_server}ok",
        },
        blocking=True,
    )

    authenticated_hass_client = await hass_client()
    resp = await authenticated_hass_client.get(
        f"/api/hass_proxy/v0/?url={urllib.parse.quote_plus(f"{local_server}ok")}"
    )
    assert resp.status == HTTPStatus.OK

    resp = await authenticated_hass_client.get(
        f"/api/hass_proxy/v0/?url={urllib.parse.quote_plus(f"{local_server}ok")}"
    )
    assert resp.status == HTTPStatus.NOT_FOUND


@pytest.mark.freeze_time()
async def test_proxy_view_dynamic_url_ttl(
    hass: HomeAssistant,
    local_server: Any,
    hass_client: Any,
    freezer: Any,
) -> None:
    """Test that a dynamic URL respects ttl."""
    config_entry = create_mock_hass_proxy_config_entry(hass, TEST_OPTIONS)

    await setup_mock_hass_proxy_config_entry(hass, config_entry)
    await async_proxy_setup_entry(hass, config_entry)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_CREATE_PROXIED_URL,
        {
            **TEST_SERVICE_CALL_PARAMS,
            CONF_TTL: 10,
            CONF_URL_PATTERN: f"{local_server}ok",
        },
        blocking=True,
    )

    authenticated_hass_client = await hass_client()
    resp = await authenticated_hass_client.get(
        f"/api/hass_proxy/v0/?url={urllib.parse.quote_plus(f"{local_server}ok")}"
    )
    assert resp.status == HTTPStatus.OK

    now = datetime.datetime.now(tz=datetime.UTC)
    freezer.move_to(now + datetime.timedelta(seconds=10 + 1))

    resp = await authenticated_hass_client.get(
        f"/api/hass_proxy/v0/?url={urllib.parse.quote_plus(f"{local_server}ok")}"
    )
    assert resp.status == HTTPStatus.GONE
