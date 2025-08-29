"""Test the proxy lib."""

from __future__ import annotations

import asyncio
import datetime
import urllib.parse
import uuid
from http import HTTPStatus
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

import aiohttp
import pytest
from homeassistant.exceptions import ServiceValidationError

from custom_components.hass_web_proxy.const import (
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
    CONF_URL_PATTERNS,
    DOMAIN,
    SERVICE_CREATE_PROXIED_URL,
    SERVICE_DELETE_PROXIED_URL,
)
from custom_components.hass_web_proxy.proxy import (
    async_setup_entry as async_proxy_setup_entry,
)
from tests import (
    create_mock_hass_web_proxy_config_entry,
    setup_mock_hass_web_proxy_config_entry,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

TEST_OPTIONS = MappingProxyType(
    {
        CONF_DYNAMIC_URLS: True,
        CONF_SSL_CIPHERS: "default",
        CONF_SSL_VERIFICATION: True,
        CONF_URL_PATTERNS: [],
    }
)

TEST_SERVICE_CALL_PARAMS = {
    CONF_OPEN_LIMIT: 0,
    CONF_SSL_CIPHERS: "default",
    CONF_SSL_VERIFICATION: True,
    CONF_TTL: 0,
}


async def test_proxy_view_success(
    hass: HomeAssistant,
    local_server: Any,
    hass_client: Any,
) -> None:
    """Test that a valid URL proxies successfully."""
    config_entry = create_mock_hass_web_proxy_config_entry(
        hass,
        MappingProxyType(
            {
                **TEST_OPTIONS,
                CONF_URL_PATTERNS: [str(local_server)],
            }
        ),
    )
    await setup_mock_hass_web_proxy_config_entry(hass, config_entry)
    await async_proxy_setup_entry(hass, config_entry)

    authenticated_hass_client = await hass_client()
    resp = await authenticated_hass_client.get(
        f"/api/hass_web_proxy/v0/?url={urllib.parse.quote_plus(str(local_server))}"
    )
    assert resp.status == HTTPStatus.OK


@pytest.mark.usefixtures("local_server")
async def test_proxy_view_without_url_parameter(
    hass: HomeAssistant,
    hass_client: Any,
) -> None:
    """Verify proxying without a url querystring parameter."""
    config_entry = create_mock_hass_web_proxy_config_entry(hass)

    await setup_mock_hass_web_proxy_config_entry(hass, config_entry)
    await async_proxy_setup_entry(hass, config_entry)

    authenticated_hass_client = await hass_client()
    resp = await authenticated_hass_client.get("/api/hass_web_proxy/v0/")
    assert resp.status == HTTPStatus.NOT_FOUND


async def test_proxy_view_no_matching_url(
    hass: HomeAssistant,
    local_server: Any,
    hass_client: Any,
) -> None:
    """Verify proxying without a matching URL."""
    config_entry = create_mock_hass_web_proxy_config_entry(
        hass,
        MappingProxyType(
            {
                **TEST_OPTIONS,
                CONF_URL_PATTERNS: [],
            }
        ),
    )
    await setup_mock_hass_web_proxy_config_entry(hass, config_entry)
    await async_proxy_setup_entry(hass, config_entry)

    authenticated_hass_client = await hass_client()
    resp = await authenticated_hass_client.get(
        f"/api/hass_web_proxy/v0/?url={urllib.parse.quote_plus(str(local_server))}"
    )
    assert resp.status == HTTPStatus.NOT_FOUND


@pytest.mark.parametrize(
    "ssl_cipher",
    [
        CONF_SSL_CIPHERS_DEFAULT,
        CONF_SSL_CIPHERS_INSECURE,
        CONF_SSL_CIPHERS_INTERMEDIATE,
        CONF_SSL_CIPHERS_MODERN,
    ],
)
async def test_proxy_view_ssl_cipher_no_verify(
    hass: HomeAssistant,
    local_server: Any,
    hass_client: Any,
    ssl_cipher: str,
) -> None:
    """Verify proxying with insecure SSL settings."""
    config_entry = create_mock_hass_web_proxy_config_entry(
        hass,
        MappingProxyType(
            {
                **TEST_OPTIONS,
                CONF_URL_PATTERNS: [str(local_server)],
                CONF_SSL_CIPHERS: ssl_cipher,
                CONF_SSL_VERIFICATION: False,
            }
        ),
    )
    await setup_mock_hass_web_proxy_config_entry(hass, config_entry)
    await async_proxy_setup_entry(hass, config_entry)

    authenticated_hass_client = await hass_client()
    resp = await authenticated_hass_client.get(
        f"/api/hass_web_proxy/v0/?url={urllib.parse.quote_plus(str(local_server))}"
    )
    assert resp.status == HTTPStatus.OK


async def test_proxy_view_dynamic_url_success(
    hass: HomeAssistant,
    local_server: Any,
    hass_client: Any,
) -> None:
    """Test that a valid dynamic URL proxies successfully."""
    config_entry = create_mock_hass_web_proxy_config_entry(hass, TEST_OPTIONS)

    await setup_mock_hass_web_proxy_config_entry(hass, config_entry)
    await async_proxy_setup_entry(hass, config_entry)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_CREATE_PROXIED_URL,
        {
            **TEST_SERVICE_CALL_PARAMS,
            CONF_URL_PATTERN: str(local_server),
        },
        blocking=True,
    )

    authenticated_hass_client = await hass_client()
    resp = await authenticated_hass_client.get(
        f"/api/hass_web_proxy/v0/?url={urllib.parse.quote_plus(str(local_server))}"
    )
    assert resp.status == HTTPStatus.OK


async def test_proxy_view_dynamic_url_return_value(
    hass: HomeAssistant,
    local_server: Any,
    hass_client: Any,
) -> None:
    """Test that a service call to create a URL returns the id."""
    config_entry = create_mock_hass_web_proxy_config_entry(hass, TEST_OPTIONS)

    await setup_mock_hass_web_proxy_config_entry(hass, config_entry)
    await async_proxy_setup_entry(hass, config_entry)

    service_response = await hass.services.async_call(
        DOMAIN,
        SERVICE_CREATE_PROXIED_URL,
        {
            **TEST_SERVICE_CALL_PARAMS,
            CONF_URL_PATTERN: str(local_server),
        },
        blocking=True,
        return_response=True,
    )

    assert service_response
    assert isinstance(service_response.get("url_id"), str)

    # Ensure the response is a valid UUID (will raise if not).
    uuid.UUID(str(service_response["url_id"]), version=4)


async def test_proxy_view_dynamic_url_delete(
    hass: HomeAssistant,
    local_server: Any,
    hass_client: Any,
) -> None:
    """Test that a dynamic URL can be deleted."""
    config_entry = create_mock_hass_web_proxy_config_entry(hass, TEST_OPTIONS)

    await setup_mock_hass_web_proxy_config_entry(hass, config_entry)
    await async_proxy_setup_entry(hass, config_entry)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_CREATE_PROXIED_URL,
        {
            **TEST_SERVICE_CALL_PARAMS,
            CONF_URL_ID: "id",
            CONF_URL_PATTERN: str(local_server),
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
        f"/api/hass_web_proxy/v0/?url={urllib.parse.quote_plus(str(local_server))}"
    )
    assert resp.status == HTTPStatus.NOT_FOUND


async def test_proxy_view_dynamic_url_delete_not_existant(hass: HomeAssistant) -> None:
    """Test that an invalid dynamic URL cannot be deleted."""
    config_entry = create_mock_hass_web_proxy_config_entry(hass, TEST_OPTIONS)

    await setup_mock_hass_web_proxy_config_entry(hass, config_entry)
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
    config_entry = create_mock_hass_web_proxy_config_entry(hass, TEST_OPTIONS)

    await setup_mock_hass_web_proxy_config_entry(hass, config_entry)
    await async_proxy_setup_entry(hass, config_entry)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_CREATE_PROXIED_URL,
        {
            **TEST_SERVICE_CALL_PARAMS,
            CONF_OPEN_LIMIT: 1,
            CONF_URL_PATTERN: str(local_server),
        },
        blocking=True,
    )

    authenticated_hass_client = await hass_client()
    resp = await authenticated_hass_client.get(
        f"/api/hass_web_proxy/v0/?url={urllib.parse.quote_plus(str(local_server))}"
    )
    assert resp.status == HTTPStatus.OK

    resp = await authenticated_hass_client.get(
        f"/api/hass_web_proxy/v0/?url={urllib.parse.quote_plus(str(local_server))}"
    )
    assert resp.status == HTTPStatus.NOT_FOUND


@pytest.mark.freeze_time
async def test_proxy_view_dynamic_url_ttl(
    hass: HomeAssistant,
    local_server: Any,
    hass_client: Any,
    freezer: Any,
) -> None:
    """Test that a dynamic URL respects ttl."""
    config_entry = create_mock_hass_web_proxy_config_entry(hass, TEST_OPTIONS)

    await setup_mock_hass_web_proxy_config_entry(hass, config_entry)
    await async_proxy_setup_entry(hass, config_entry)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_CREATE_PROXIED_URL,
        {
            **TEST_SERVICE_CALL_PARAMS,
            CONF_TTL: 10,
            CONF_URL_PATTERN: str(local_server),
        },
        blocking=True,
    )

    authenticated_hass_client = await hass_client()
    resp = await authenticated_hass_client.get(
        f"/api/hass_web_proxy/v0/?url={urllib.parse.quote_plus(str(local_server))}"
    )
    assert resp.status == HTTPStatus.OK

    now = datetime.datetime.now(tz=datetime.UTC)
    freezer.move_to(now + datetime.timedelta(seconds=10 + 1))

    resp = await authenticated_hass_client.get(
        f"/api/hass_web_proxy/v0/?url={urllib.parse.quote_plus(str(local_server))}"
    )
    assert resp.status == HTTPStatus.NOT_FOUND


async def test_proxy_view_dynamic_url_unauthenticated_forbidden(
    hass: HomeAssistant,
    local_server: Any,
    hass_client_no_auth: Any,
) -> None:
    """Test that a valid dynamic URL is rejected for unauthorized users."""
    config_entry = create_mock_hass_web_proxy_config_entry(hass, TEST_OPTIONS)

    await setup_mock_hass_web_proxy_config_entry(hass, config_entry)
    await async_proxy_setup_entry(hass, config_entry)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_CREATE_PROXIED_URL,
        {
            **TEST_SERVICE_CALL_PARAMS,
            CONF_URL_PATTERN: str(local_server),
        },
        blocking=True,
    )

    unauthenticated_hass_client = await hass_client_no_auth()
    resp = await unauthenticated_hass_client.get(
        f"/api/hass_web_proxy/v0/?url={urllib.parse.quote_plus(str(local_server))}"
    )
    assert resp.status == HTTPStatus.UNAUTHORIZED


async def test_proxy_view_dynamic_url_unauthenticated_permitted(
    hass: HomeAssistant,
    local_server: Any,
    hass_client_no_auth: Any,
) -> None:
    """Test that a valid dynamic URL is permitted for unauthorized users."""
    config_entry = create_mock_hass_web_proxy_config_entry(hass, TEST_OPTIONS)

    await setup_mock_hass_web_proxy_config_entry(hass, config_entry)
    await async_proxy_setup_entry(hass, config_entry)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_CREATE_PROXIED_URL,
        {
            **TEST_SERVICE_CALL_PARAMS,
            CONF_URL_PATTERN: str(local_server),
            CONF_ALLOW_UNAUTHENTICATED: True,
        },
        blocking=True,
    )

    unauthenticated_hass_client = await hass_client_no_auth()
    resp = await unauthenticated_hass_client.get(
        f"/api/hass_web_proxy/v0/?url={urllib.parse.quote_plus(str(local_server))}"
    )
    assert resp.status == HTTPStatus.OK


async def test_proxy_websocket_view_success(
    hass: HomeAssistant,
    local_server: Any,
    hass_client: Any,
) -> None:
    """Test that a valid URL proxies successfully."""
    config_entry = create_mock_hass_web_proxy_config_entry(hass, TEST_OPTIONS)

    await setup_mock_hass_web_proxy_config_entry(hass, config_entry)
    await async_proxy_setup_entry(hass, config_entry)

    url_to_proxy = str(local_server) + "ws"

    await hass.services.async_call(
        DOMAIN,
        SERVICE_CREATE_PROXIED_URL,
        {
            **TEST_SERVICE_CALL_PARAMS,
            CONF_URL_PATTERN: url_to_proxy,
        },
        blocking=True,
    )

    authenticated_hass_client = await hass_client()

    async with authenticated_hass_client.ws_connect(
        f"/api/hass_web_proxy/v0/ws?url={urllib.parse.quote_plus(url_to_proxy)}"
    ) as ws:
        await ws.ping()

        request = await ws.receive_json()
        assert request["url"] == f"{local_server}ws"

        # Test sending text data.
        result = await asyncio.gather(
            ws.send_str("hello!"),
            ws.receive(),
        )
        assert result[1].type == aiohttp.WSMsgType.TEXT
        assert result[1].data == "hello!"
