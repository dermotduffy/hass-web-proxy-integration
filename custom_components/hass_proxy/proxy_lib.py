"""HASS Proxy proxy."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from http import HTTPStatus
from ipaddress import ip_address
from typing import TYPE_CHECKING, Any

import aiohttp
from aiohttp import hdrs, web
from aiohttp.web_exceptions import HTTPBadGateway
from homeassistant.components.http import HomeAssistantView
from homeassistant.util.ssl import get_default_context

from .const import LOGGER

if TYPE_CHECKING:
    import ssl
    from collections.abc import Mapping

    from multidict import CIMultiDict


class HASSProxyLibError(Exception):
    """Exception to indicate a general Proxy error."""


class HASSProxyLibBadRequestError(HASSProxyLibError):
    """Exception to indicate a bad request."""


class HASSProxyLibForbiddenRequestError(HASSProxyLibError):
    """Exception to indicate a bad request."""


class HASSProxyLibNotFoundRequestError(HASSProxyLibError):
    """Exception to indicate something being not found."""


class HASSProxyLibExpiredError(HASSProxyLibError):
    """Exception to indicate a URL match that has expired."""


# These proxies are inspired by:
#  - https://github.com/home-assistant/supervisor/blob/main/supervisor/api/ingress.py
#  - https://github.com/blakeblackshear/frigate-hass-integration/blob/master/custom_components/frigate/views.py


@dataclass
class ProxiedURL:
    """A proxied URL."""

    url: str
    ssl_context: ssl.SSLContext | None = None


class ProxyView(HomeAssistantView):  # type: ignore[misc]
    """HomeAssistant view."""

    # TODO(dermotduffy): Change to true.
    requires_auth = False

    def __init__(
        self,
        websession: aiohttp.ClientSession,
    ) -> None:
        """Initialize the HASS Proxy view."""
        self._websession = websession

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

    def _get_proxied_url_or_handle_error(
        self,
        request: web.Request,
        **kwargs: Any,
    ) -> ProxiedURL | web.Response:
        """Get the proxied URL or handle error."""
        try:
            url = self._get_proxied_url(request, **kwargs)
        except HASSProxyLibForbiddenRequestError:
            return web.Response(status=HTTPStatus.FORBIDDEN)
        except HASSProxyLibNotFoundRequestError:
            return web.Response(status=HTTPStatus.NOT_FOUND)
        except HASSProxyLibBadRequestError:
            return web.Response(status=HTTPStatus.BAD_REQUEST)
        except HASSProxyLibExpiredError:
            return web.Response(status=HTTPStatus.GONE)

        if not url or not url.url:
            return web.Response(status=HTTPStatus.NOT_FOUND)
        return url

    def _get_proxied_url(self, _request: web.Request, **_kwargs: Any) -> ProxiedURL:
        """Get the relevant Proxied URL."""
        raise NotImplementedError  # pragma: no cover

    async def _handle_request(
        self,
        request: web.Request,
        **kwargs: Any,
    ) -> web.Response | web.StreamResponse:
        """Handle route for request."""
        LOGGER.debug("PROXY REQUEST: %s", request)

        url_or_response = self._get_proxied_url_or_handle_error(request, **kwargs)
        if isinstance(url_or_response, web.Response):
            return url_or_response

        data = await request.read()
        source_header = _init_header(request)

        async with self._websession.request(
            request.method,
            url_or_response.url,
            headers=source_header,
            params=self._get_query_params(request),
            allow_redirects=False,
            data=data,
            ssl=url_or_response.ssl_context or get_default_context(),
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
        url_or_response = self._get_proxied_url_or_handle_error(request, **kwargs)
        if isinstance(url_or_response, web.Response):
            return url_or_response

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

        source_header = _init_header(request)

        # TODO: Why is this only here?
        url = (
            url_or_response.url
            if not request.query_string
            else f"{url_or_response.url}?{request.query_string}"
        )

        async with self._websession.ws_connect(
            url,
            headers=source_header,
            protocols=req_protocols,
            autoclose=False,
            autoping=False,
            ssl=url_or_response.ssl_context or get_default_context(),
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
