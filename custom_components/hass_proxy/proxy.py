"""HASS Proxy proxy."""

from __future__ import annotations

import asyncio
import ssl
import urllib
from http import HTTPStatus
from ipaddress import ip_address
from typing import TYPE_CHECKING, Any

import aiohttp
from aiohttp import hdrs, web
from aiohttp.web_exceptions import HTTPBadGateway
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.http.const import KEY_HASS
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.hass_proxy.const import DOMAIN

from .const import LOGGER

if TYPE_CHECKING:
    from collections.abc import Mapping
    from types import MappingProxyType

    from homeassistant.core import HomeAssistant
    from multidict import CIMultiDict


def async_setup(hass: HomeAssistant) -> None:
    """Set up the views."""
    session = async_get_clientsession(hass)
    hass.http.register_view(V0ProxyView(session))


class HASSProxyError(Exception):
    """Exception to indicate a general Proxy error."""


class HASSProxyBadRequestError(Exception):
    """Exception to indicate a bad request."""


class HASSProxyNotFoundRequestError(Exception):
    """Exception to indicate something being not found."""


# These proxies are inspired by:
#  - https://github.com/home-assistant/supervisor/blob/main/supervisor/api/ingress.py
#  - https://github.com/blakeblackshear/frigate-hass-integration/blob/master/custom_components/frigate/views.py


class ProxyView(HomeAssistantView):  # type: ignore[misc]
    """HomeAssistant view."""

    # TODO(dermotduffy): Change to true.
    requires_auth = False

    def __init__(self, websession: aiohttp.ClientSession) -> None:
        """Initialize the HASS Proxy view."""
        self._websession = websession

    def _get_options(self, request: web.Request) -> MappingProxyType[str, Any]:
        """Get a ConfigEntry options for a given request."""
        hass = request.app[KEY_HASS]
        return hass.config_entries.async_entries(DOMAIN)[0].options

    def _get_url(self, _request: web.Request, **_kwargs: Any) -> str:
        """Get the relevant URL to proxy."""
        raise NotImplementedError  # pragma: no cover

    def _permit_request(
        self,
        _request: web.Request,
        _options: MappingProxyType[str, Any],
        **_kwargs: Any,
    ) -> bool:
        """Determine whether to permit a request."""
        return True

    async def get(
        self,
        request: web.Request,
        **kwargs: Any,
    ) -> web.Response | web.StreamResponse | web.WebSocketResponse:
        """Route data to service."""
        try:
            return await self._handle_request(request, **kwargs)
        except aiohttp.ClientError as err:
            LOGGER.debug("Reverse proxy error for %s: %s", request.rel_url, err)
        raise HTTPBadGateway

    @staticmethod
    def _get_query_params(request: web.Request) -> Mapping[str, str]:
        """Get the query params to send upstream."""
        return {k: v for k, v in request.query.items() if k != "authSig"}

    async def _handle_request(
        self,
        request: web.Request,
        **kwargs: Any,
    ) -> web.Response | web.StreamResponse:
        """Handle route for request."""
        LOGGER.debug("PROXY REQUEST: %s", request)

        options = self._get_options(request)

        if not self._permit_request(request, options, **kwargs):
            LOGGER.debug("NO PERMS: %s", request)
            return web.Response(status=HTTPStatus.FORBIDDEN)
        try:
            url = self._get_url(request, **kwargs)
        except HASSProxyNotFoundRequestError:
            LOGGER.debug("NOT FOUND: %s", request)
            return web.Response(status=HTTPStatus.NOT_FOUND)
        except HASSProxyBadRequestError:
            LOGGER.debug("BAD: %s", request)
            return web.Response(status=HTTPStatus.BAD_REQUEST)

        if not url:
            LOGGER.debug("NO URL: %s", request)
            return web.Response(status=HTTPStatus.NOT_FOUND)

        data = await request.read()
        source_header = _init_header(request)

        ssl_context = ssl.create_default_context()
        ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2  # Set minimum TLS version


        ssl_context.set_ciphers("DEFAULT")
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_context))

        async with session.request(
            request.method,
            url,
            headers=source_header,
            params=self._get_query_params(request),
            allow_redirects=False,
            data=data,
            # TODO: Configurable
            # TODO: below also?

        ) as result:
            headers = _response_header(result)

            # Stream response
            response = web.StreamResponse(status=result.status, headers=headers)
            response.content_type = result.content_type

            try:
                await response.prepare(request)
                async for data in result.content.iter_any():
                    await response.write(data)

            except (aiohttp.ClientError, aiohttp.ClientPayloadError) as err:
                LOGGER.debug("Stream error for %s: %s", request.rel_url, err)
            except ConnectionResetError:
                # Connection is reset/closed by peer.
                pass

            return response


class V0ProxyView(ProxyView):
    """A proxy for snapshots."""

    url = "/api/hass_proxy/v0/"

    name = "api:hass_proxy:v0"

    def _get_url(self, request: web.Request, **_kwargs: Any) -> str:
        """Create path."""
        qs = request.query
        LOGGER.debug("PROXY URL: %s", qs)
        if "url" not in qs:
            raise HASSProxyNotFoundRequestError
        return urllib.parse.unquote(qs["url"])


class WebsocketProxyView(ProxyView):
    """A simple proxy for websockets."""

    async def _proxy_msgs(
        self,
        ws_in: aiohttp.ClientWebSocketResponse | web.WebSocketResponse,
        ws_out: aiohttp.ClientWebSocketResponse | web.WebSocketResponse,
    ) -> None:
        async for msg in ws_in:
            try:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    await ws_out.send_str(msg.data)
                elif msg.type == aiohttp.WSMsgType.BINARY:
                    await ws_out.send_bytes(msg.data)
                elif msg.type == aiohttp.WSMsgType.PING:
                    await ws_out.ping()
                elif msg.type == aiohttp.WSMsgType.PONG:
                    await ws_out.pong()
            except ConnectionResetError:
                return

    async def _handle_request(
        self,
        request: web.Request,
        **kwargs: Any,
    ) -> web.Response | web.StreamResponse:
        """Handle route for request."""
        options = self._get_options(request)
        if not options:
            return web.Response(status=HTTPStatus.BAD_REQUEST)

        if not self._permit_request(request, options, **kwargs):
            return web.Response(status=HTTPStatus.FORBIDDEN)
        try:
            url = self._get_url(request, **kwargs)
        except HASSProxyNotFoundRequestError:
            return web.Response(status=HTTPStatus.NOT_FOUND)
        except HASSProxyBadRequestError:
            return web.Response(status=HTTPStatus.BAD_REQUEST)

        if not url:
            return web.Response(status=HTTPStatus.NOT_FOUND)

        req_protocols = []
        if hdrs.SEC_WEBSOCKET_PROTOCOL in request.headers:
            req_protocols = [
                str(proto.strip())
                for proto in request.headers[hdrs.SEC_WEBSOCKET_PROTOCOL].split(",")
            ]

        ws_to_user = web.WebSocketResponse(
            protocols=req_protocols, autoclose=False, autoping=False
        )
        await ws_to_user.prepare(request)

        # Preparing
        source_header = _init_header(request)

        # Support GET query
        if request.query_string:
            url = f"{url}?{request.query_string}"

        async with self._websession.ws_connect(
            url,
            headers=source_header,
            protocols=req_protocols,
            autoclose=False,
            autoping=False,
            # TODO
            ssl=False,
        ) as ws_to_target:
            await asyncio.wait(
                [
                    asyncio.create_task(self._proxy_msgs(ws_to_target, ws_to_user)),
                    asyncio.create_task(self._proxy_msgs(ws_to_user, ws_to_target)),
                ],
                return_when=asyncio.tasks.FIRST_COMPLETED,
            )
        return ws_to_user


def _init_header(request: web.Request) -> CIMultiDict | dict[str, str]:
    """Create initial header."""
    headers = {}

    # filter flags
    for name, value in request.headers.items():
        if name in (
            hdrs.CONTENT_LENGTH,
            hdrs.CONTENT_ENCODING,
            hdrs.SEC_WEBSOCKET_EXTENSIONS,
            hdrs.SEC_WEBSOCKET_PROTOCOL,
            hdrs.SEC_WEBSOCKET_VERSION,
            hdrs.SEC_WEBSOCKET_KEY,
            hdrs.HOST,
            hdrs.AUTHORIZATION,
        ):
            continue
        headers[name] = value

    # Set X-Forwarded-For
    forward_for = request.headers.get(hdrs.X_FORWARDED_FOR)
    connected_ip = ip_address(request.transport.get_extra_info("peername")[0])
    if forward_for:
        forward_for = f"{forward_for}, {connected_ip!s}"
    else:
        forward_for = f"{connected_ip!s}"
    headers[hdrs.X_FORWARDED_FOR] = forward_for

    # Set X-Forwarded-Host
    forward_host = request.headers.get(hdrs.X_FORWARDED_HOST)
    if not forward_host:
        forward_host = request.host
    headers[hdrs.X_FORWARDED_HOST] = forward_host

    # Set X-Forwarded-Proto
    forward_proto = request.headers.get(hdrs.X_FORWARDED_PROTO)
    if not forward_proto:
        forward_proto = request.url.scheme
    headers[hdrs.X_FORWARDED_PROTO] = forward_proto

    return headers


def _response_header(response: aiohttp.ClientResponse) -> dict[str, str]:
    """Create response header."""
    headers = {}

    for name, value in response.headers.items():
        if name in (
            hdrs.TRANSFER_ENCODING,
            # Removing Content-Length header for streaming responses
            #   prevents seeking from working for mp4 files
            # hdrs.CONTENT_LENGTH,
            hdrs.CONTENT_TYPE,
            hdrs.CONTENT_ENCODING,
            # Strips inbound CORS response headers since the aiohttp_cors
            # library will assert that they are not already present for CORS
            # requests.
            hdrs.ACCESS_CONTROL_ALLOW_ORIGIN,
            hdrs.ACCESS_CONTROL_ALLOW_CREDENTIALS,
            hdrs.ACCESS_CONTROL_EXPOSE_HEADERS,
        ):
            continue
        headers[name] = value

    return headers
