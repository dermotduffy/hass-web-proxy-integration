"""Test the proxy lib."""

from __future__ import annotations

import asyncio
from http import HTTPStatus
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import aiohttp
import pytest
from aiohttp import hdrs

from custom_components.hass_proxy import proxy_lib
from custom_components.hass_proxy.proxy_lib import (
    HASSProxyLibBadRequestError,
    HASSProxyLibExpiredError,
    HASSProxyLibForbiddenRequestError,
    HASSProxyLibNotFoundRequestError,
    ProxiedURL,
    WebsocketProxyView,
)
from tests.utils import (
    TEST_PROXY_URL,
    ClientErrorStreamResponse,
    ConnectionResetStreamResponse,
    FakeAsyncContextManager,
    register_test_view,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


async def test_proxy_view_http_ok(
    hass: HomeAssistant,
    local_server: Any,
    hass_client: Any,
) -> None:
    """Test that a valid URL causes OK."""
    await register_test_view(hass, proxied_url=ProxiedURL(url=f"{local_server}ok"))

    authenticated_hass_client = await hass_client()
    resp = await authenticated_hass_client.get(TEST_PROXY_URL)
    assert resp.status == HTTPStatus.OK


async def test_proxy_view_http_ok_header_verify(
    hass: HomeAssistant,
    local_server: Any,
    hass_client: Any,
) -> None:
    """Test that a valid URL causes OK."""
    await register_test_view(hass, proxied_url=ProxiedURL(url=f"{local_server}ok"))

    authenticated_hass_client = await hass_client()
    source_headers = {
        hdrs.HOST: "example.com",
        hdrs.X_FORWARDED_FOR: "192.168.0.1",
        "my-header": "my-value",
    }
    resp = await authenticated_hass_client.get(TEST_PROXY_URL, headers=source_headers)
    assert resp.status == HTTPStatus.OK

    request_headers = await resp.json()
    assert request_headers["my-header"] == "my-value"
    assert request_headers[hdrs.X_FORWARDED_FOR] == "192.168.0.1, 127.0.0.1"
    assert request_headers[hdrs.X_FORWARDED_HOST] == "example.com"
    assert request_headers[hdrs.X_FORWARDED_PROTO] == "http"


@pytest.mark.usefixtures("local_server")
async def test_proxy_view_http_not_found(
    hass: HomeAssistant,
    hass_client: Any,
) -> None:
    """Test that a missing URL causes NOT_FOUND."""
    await register_test_view(hass, exception=HASSProxyLibNotFoundRequestError)

    authenticated_hass_client = await hass_client()
    resp = await authenticated_hass_client.get(TEST_PROXY_URL)
    assert resp.status == HTTPStatus.NOT_FOUND


@pytest.mark.usefixtures("local_server")
async def test_proxy_view_http_forbidden(
    hass: HomeAssistant,
    hass_client: Any,
) -> None:
    """Test that a forbidden URL causes FORBIDDEN."""
    await register_test_view(hass, exception=HASSProxyLibForbiddenRequestError)

    authenticated_hass_client = await hass_client()
    resp = await authenticated_hass_client.get(TEST_PROXY_URL)
    assert resp.status == HTTPStatus.FORBIDDEN


@pytest.mark.usefixtures("local_server")
async def test_proxy_view_http_gone(
    hass: HomeAssistant,
    hass_client: Any,
) -> None:
    """Test that an old URL causes GONE."""
    await register_test_view(hass, exception=HASSProxyLibExpiredError)

    authenticated_hass_client = await hass_client()
    resp = await authenticated_hass_client.get(TEST_PROXY_URL)
    assert resp.status == HTTPStatus.GONE


@pytest.mark.usefixtures("local_server")
async def test_proxy_view_http_bad_request(
    hass: HomeAssistant,
    hass_client: Any,
) -> None:
    """Test that an bad request causes BAD_REQUEST."""
    await register_test_view(hass, exception=HASSProxyLibBadRequestError)

    authenticated_hass_client = await hass_client()
    resp = await authenticated_hass_client.get(TEST_PROXY_URL)
    assert resp.status == HTTPStatus.BAD_REQUEST


@pytest.mark.usefixtures("local_server")
async def test_proxy_view_empty_proxied_url(
    hass: HomeAssistant,
    hass_client: Any,
) -> None:
    """Test that an empty proxied URL causes NOT_FOUND."""
    await register_test_view(hass, proxied_url=ProxiedURL(""))

    authenticated_hass_client = await hass_client()
    resp = await authenticated_hass_client.get(TEST_PROXY_URL)
    assert resp.status == HTTPStatus.NOT_FOUND


async def test_proxy_view_aiohttp_write_error(
    caplog: Any,
    hass: HomeAssistant,
    local_server: Any,
    hass_client: Any,
) -> None:
    """Test that an aiohttp error is handled."""
    await register_test_view(hass, proxied_url=ProxiedURL(url=f"{local_server}ok"))

    authenticated_hass_client = await hass_client()

    with patch(
        "custom_components.hass_proxy.proxy_lib.web.StreamResponse",
        new=ClientErrorStreamResponse,
    ):
        await authenticated_hass_client.get(TEST_PROXY_URL)
        assert "Stream error" in caplog.text


async def test_proxy_view_aiohttp_connection_reset_error(
    caplog: Any,
    hass: HomeAssistant,
    local_server: Any,
    hass_client: Any,
) -> None:
    """Test that an aiohttp connection reset is handled."""
    await register_test_view(hass, proxied_url=ProxiedURL(url=f"{local_server}ok"))

    authenticated_hass_client = await hass_client()

    with patch(
        "custom_components.hass_proxy.proxy_lib.web.StreamResponse",
        new=ConnectionResetStreamResponse,
    ):
        await authenticated_hass_client.get(TEST_PROXY_URL)
        assert "Stream error" not in caplog.text


async def test_proxy_view_aiohttp_read_error(
    hass: HomeAssistant,
    caplog: Any,
    local_server: Any,
    hass_client: Any,
) -> None:
    """Test snapshot request with a read error."""
    await register_test_view(hass, proxied_url=ProxiedURL(url=f"{local_server}ok"))

    authenticated_hass_client = await hass_client()

    mock_request = MagicMock(FakeAsyncContextManager())
    mock_request.side_effect = aiohttp.ClientError

    with patch.object(
        hass.helpers.aiohttp_client.async_get_clientsession(),
        "request",
        new=mock_request,
    ):
        await authenticated_hass_client.get(TEST_PROXY_URL)
        assert "Reverse proxy error" in caplog.text


async def test_headers(
    hass: HomeAssistant,
    local_server: Any,
    hass_client_no_auth: Any,
) -> None:
    """Test proxy headers are added and respected."""
    unauthenticated_hass_client = await hass_client_no_auth()

    await register_test_view(hass, proxied_url=ProxiedURL(url=f"{local_server}ok"))

    resp = await unauthenticated_hass_client.get(
        TEST_PROXY_URL,
        headers={hdrs.CONTENT_ENCODING: "foo"},
    )
    assert resp.status == HTTPStatus.OK

    resp = await unauthenticated_hass_client.get(
        TEST_PROXY_URL,
        headers={hdrs.X_FORWARDED_FOR: "1.2.3.4"},
    )
    assert resp.status == HTTPStatus.OK


async def test_proxy_view_websocket_ok(
    hass: Any,
    local_server: Any,
    hass_client: Any,
) -> None:
    """Test proxying websocket connection."""
    await register_test_view(
        hass, proxied_url=ProxiedURL(url=f"{local_server}ws"), kind=WebsocketProxyView
    )

    authenticated_hass_client = await hass_client()

    async with authenticated_hass_client.ws_connect(TEST_PROXY_URL) as ws:
        await ws.ping()

        # Test sending text data.
        result = await asyncio.gather(
            ws.send_str("hello!"),
            ws.receive(),
        )
        assert result[1].type == aiohttp.WSMsgType.TEXT
        assert result[1].data == "hello!"

        # # Test sending binary data.
        result = await asyncio.gather(
            ws.send_bytes(b"\x00\x01"),
            ws.receive(),
        )

        assert result[1].type == aiohttp.WSMsgType.BINARY
        assert result[1].data == b"\x00\x01"


async def test_proxy_view_websocket_connection_reset(
    hass: Any,
    local_server: Any,
    hass_client: Any,
) -> None:
    """Test proxy websocket handles connection resets."""
    await register_test_view(
        hass, proxied_url=ProxiedURL(url=f"{local_server}ws"), kind=WebsocketProxyView
    )

    # Tricky: This test is intended to test a ConnectionResetError to the
    # backend server, which is the _second_ call to send*. The first call (from
    # this test) needs to succeed.
    real_send_str = proxy_lib.aiohttp.web.WebSocketResponse.send_str
    called_once = False

    async def send_str(*args: Any, **kwargs: Any) -> None:
        nonlocal called_once
        if called_once:
            raise ConnectionResetError
        called_once = True
        return await real_send_str(*args, **kwargs)

    authenticated_hass_client = await hass_client()

    with patch(
        "custom_components.hass_proxy.proxy_lib.aiohttp.ClientWebSocketResponse.send_str",
        new=send_str,
    ):
        async with authenticated_hass_client.ws_connect(TEST_PROXY_URL) as ws:
            await ws.send_str("data")


@pytest.mark.usefixtures("local_server")
async def test_proxy_view_websocket_non_ok(
    hass: HomeAssistant,
    hass_client: Any,
) -> None:
    """Test that an invalid ProxiedURL for a websocket proxy is handled."""
    await register_test_view(
        hass, exception=HASSProxyLibNotFoundRequestError, kind=WebsocketProxyView
    )

    authenticated_hass_client = await hass_client()
    resp = await authenticated_hass_client.get(TEST_PROXY_URL)
    assert resp.status == HTTPStatus.NOT_FOUND


async def test_ws_proxy_specify_protocol(
    hass: Any,
    local_server: Any,
    hass_client: Any,
) -> None:
    """Test websocket proxy handles the SEC_WEBSOCKET_PROTOCOL header."""
    await register_test_view(
        hass, proxied_url=ProxiedURL(url=f"{local_server}ws"), kind=WebsocketProxyView
    )

    authenticated_hass_client = await hass_client()

    async with authenticated_hass_client.ws_connect(
        TEST_PROXY_URL, headers={hdrs.SEC_WEBSOCKET_PROTOCOL: "foo,bar"}
    ) as ws:
        assert ws
        await ws.close()
