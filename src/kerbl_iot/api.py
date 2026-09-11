"""HTTP client for the confirmed Kerbl IoT API endpoints."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

import aiohttp
import socketio

from .exceptions import (
    KerblAuthenticationError,
    KerblConnectionError,
    KerblProtocolError,
)
from .models import CommandResult, SmartCoop, SmartCoopLog

BASE_URL = "https://app.kerbl-iot.com/api/v0.1/"
SOCKET_URL = "https://app.kerbl-iot.com"
SOCKET_PATH = "ws/v0.1/socket.io"


class KerblIOTApi:
    """Authenticate with and retrieve data from Kerbl IoT."""

    def __init__(
        self,
        email: str,
        password: str,
        timeout: float = 15.0,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be greater than zero.")
        self._email = email
        self._password = password
        self._timeout = timeout
        self._provided_session = session
        self._session = session
        self._session_owned = False
        self._socket: socketio.AsyncClient | None = None
        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._refresh_lock = asyncio.Lock()
        self._smart_coop_update_callbacks: list[Callable[[SmartCoop], Awaitable[None]]] = []
        self._socket_event_callbacks: list[
            Callable[[str, Any], Awaitable[None]]
        ] = []
        self._socket_disconnect_callbacks: list[Callable[[], Awaitable[None]]] = []
        self._socket_connect_callbacks: list[Callable[[], Awaitable[None]]] = []
        self._subscribed_device_ids: list[str] = []
        self._socket_user_id: str | None = None

    async def __aenter__(self) -> "KerblIOTApi":
        await self.login()
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()

    async def close(self) -> None:
        """Close the underlying HTTP session."""
        socket, session = self._socket, self._session
        self._socket = None
        self._session = None
        self._access_token = None
        self._refresh_token = None
        try:
            if socket is not None and socket.connected and self._socket_user_id is not None:
                await socket.emit(
                    "leave_room",
                    {
                        "deviceIds": self._subscribed_device_ids,
                        "userId": self._socket_user_id,
                    },
                )
        finally:
            self._subscribed_device_ids = []
            self._socket_user_id = None
            try:
                if socket is not None:
                    await socket.disconnect()
            finally:
                if session is not None and self._session_owned:
                    await session.close()
                self._session_owned = False

    async def login(self) -> dict[str, Any]:
        """Sign in using the request format captured from the web application."""
        await self.close()
        if self._provided_session is not None:
            self._session = self._provided_session
        else:
            self._session = aiohttp.ClientSession(
                base_url=BASE_URL,
                headers={"Accept": "application/json"},
                timeout=aiohttp.ClientTimeout(total=self._timeout),
                raise_for_status=True,
            )
            self._session_owned = True
        payload = {
            "email": self._email,
            "password": self._password,
            "appBrand": "kerbl",
            "appVersion": "137.6.1",
            "loginId": str(uuid.uuid4()),
        }
        try:
            authentication = await self._request_json(
                "POST", "auth/sign-in", payload, refresh_on_unauthorized=False
            )
            self._set_authentication(authentication)
        except Exception:
            await self.close()
            raise

        return authentication

    async def refresh_token(self) -> None:
        """Refresh the access token using the token pair from the last login."""
        async with self._refresh_lock:
            if not self._access_token or not self._refresh_token:
                raise KerblAuthenticationError("No refresh token is available.")
            try:
                authentication = await self._request_json(
                    "POST",
                    "auth/refresh",
                    {
                        "accessToken": self._access_token,
                        "refreshToken": self._refresh_token,
                    },
                    refresh_on_unauthorized=False,
                )
                self._set_authentication(authentication)
            except (KerblAuthenticationError, KerblConnectionError, KerblProtocolError):
                raise

    def get_tokens(self) -> tuple[str, str]:
        """Return the access and refresh tokens for persistent storage."""
        if not self._access_token or not self._refresh_token:
            raise KerblAuthenticationError("No authentication tokens are available.")
        return self._access_token, self._refresh_token

    def restore_tokens(self, access_token: str, refresh_token: str) -> None:
        """Restore tokens from persistent storage without signing in again."""
        self._set_authentication(
            {"accessToken": access_token, "refreshToken": refresh_token}
        )

    def _set_authentication(self, authentication: dict[str, Any]) -> None:
        access_token = authentication.get("accessToken")
        refresh_token = authentication.get("refreshToken")
        if not isinstance(access_token, str) or not access_token:
            raise KerblAuthenticationError("Kerbl response did not include an access token.")
        if not isinstance(refresh_token, str) or not refresh_token:
            raise KerblAuthenticationError("Kerbl response did not include a refresh token.")
        self._access_token = access_token
        self._refresh_token = refresh_token
        self._require_session().headers["Authorization"] = f"Bearer {access_token}"

    async def _request_json(
        self,
        method: str,
        endpoint: str,
        payload: dict[str, Any] | None = None,
        *,
        refresh_on_unauthorized: bool = True,
    ) -> dict[str, Any]:
        """Send one JSON request and refresh the access token once after a 401."""
        session = self._require_session()
        request_url = endpoint if self._provided_session is None else f"{BASE_URL}{endpoint}"
        try:
            async with session.request(method, request_url, json=payload) as response:
                return await response.json()
        except aiohttp.ClientResponseError as error:
            if error.status == 401 and refresh_on_unauthorized:
                await self.refresh_token()
                return await self._request_json(
                    method, endpoint, payload, refresh_on_unauthorized=False
                )
            if error.status == 401:
                raise KerblAuthenticationError("Kerbl rejected the request.") from error
            raise KerblConnectionError("Kerbl IoT service returned an HTTP error.") from error
        except (aiohttp.ClientError, asyncio.TimeoutError) as error:
            raise KerblConnectionError("Kerbl IoT service could not be reached.") from error
        except (TypeError, ValueError) as error:
            raise KerblProtocolError("Kerbl returned an invalid JSON response.") from error

    async def get_smart_coops(self) -> list[SmartCoop]:
        """Retrieve all SmartCoop devices assigned to the current user."""
        devices = await self._request_json("GET", "device")
        return [SmartCoop.from_api(data, self) for data in devices.get("smartCoop", [])]

    async def get_smart_coop_logs(self, smart_coop_id: str) -> list[SmartCoopLog]:
        """Retrieve error and informational logs for one SmartCoop."""
        endpoint = f"device/smart-coop/{smart_coop_id}/log"
        payload = await self._request_json("GET", endpoint)
        return [SmartCoopLog.from_api(data) for data in payload.get("logs", [])]

    async def _press_light(self, smart_coop_id: str) -> CommandResult:
        """Press a SmartCoop light using its confirmed manual-control command."""
        endpoint = f"device/smart-coop/{smart_coop_id}/command/lightControl"
        return CommandResult.from_api(await self._request_json("PATCH", endpoint, {"value": 1}))

    async def _press_feeder(self, smart_coop_id: str) -> CommandResult:
        """Press a SmartCoop feeder using its confirmed manual-control command."""
        endpoint = f"device/smart-coop/{smart_coop_id}/command/feederControl"
        return CommandResult.from_api(await self._request_json("PATCH", endpoint, {"value": 1}))

    async def _press_door(self, smart_coop_id: str) -> CommandResult:
        """Press a SmartCoop door using its confirmed manual-control command."""
        endpoint = f"device/smart-coop/{smart_coop_id}/command/doorControl"
        return CommandResult.from_api(await self._request_json("PATCH", endpoint, {"value": 1}))

    async def _acknowledge_errors(
        self, smart_coop_id: str, error_codes: list[int]
    ) -> CommandResult:
        """Acknowledge one or more active SmartCoop error codes."""
        if not error_codes:
            raise ValueError("Provide at least one error code to acknowledge.")

        endpoint = f"device/smart-coop/{smart_coop_id}/command/acknowledgeErrorControl"
        return CommandResult.from_api(
            await self._request_json("PATCH", endpoint, {"value": error_codes})
        )

    async def connect_websocket(
        self, smart_coops: list[SmartCoop], debug: bool = False
    ) -> None:
        """Connect to Socket.IO and subscribe to updates for all SmartCoops."""
        if self.websocket_connected:
            return

        if not smart_coops:
            return

        session = self._require_session()
        socket = socketio.AsyncClient(
            reconnection=True,
            logger=debug,
            engineio_logger=debug,
        )
        socket.on("smart-coop_update", self._handle_smart_coop_update)
        socket.on("*", self._handle_socket_event)
        socket.on("connect", self._handle_socket_connect)
        socket.on("disconnect", self._handle_socket_disconnect)
        try:
            await socket.connect(
                SOCKET_URL,
                socketio_path=SOCKET_PATH,
                headers={"Authorization": session.headers["Authorization"]},
            )
            self._subscribed_device_ids = [coop.id for coop in smart_coops]
            self._socket_user_id = smart_coops[0].user_id
            await socket.emit(
                "join_room",
                {
                    "deviceIds": self._subscribed_device_ids,
                    "userId": self._socket_user_id,
                },
            )
        except (aiohttp.ClientError, socketio.exceptions.ConnectionError, asyncio.TimeoutError) as error:
            await socket.disconnect()
            self._subscribed_device_ids = []
            self._socket_user_id = None
            raise KerblConnectionError("Kerbl WebSocket could not be connected.") from error
        self._socket = socket

    async def _handle_socket_connect(self) -> None:
        """Rejoin subscribed SmartCoop rooms after a Socket.IO reconnect."""
        if self._socket is not None and self._socket_user_id is not None:
            await self._socket.emit(
                "join_room",
                {
                    "deviceIds": self._subscribed_device_ids,
                    "userId": self._socket_user_id,
                },
            )
        for callback in self._socket_connect_callbacks:
            await callback()

    @property
    def websocket_connected(self) -> bool:
        """Return whether the Socket.IO connection is active."""
        return self._socket is not None and self._socket.connected

    def register_smart_coop_update_callback(
        self, callback: Callable[[SmartCoop], Awaitable[None]]
    ) -> None:
        """Register an asynchronous callback for SmartCoop Socket.IO updates."""
        self._smart_coop_update_callbacks.append(callback)

    def register_socket_event_callback(
        self, callback: Callable[[str, Any], Awaitable[None]]
    ) -> None:
        """Register an asynchronous callback for all Socket.IO server events."""
        self._socket_event_callbacks.append(callback)

    def register_socket_disconnect_callback(
        self, callback: Callable[[], Awaitable[None]]
    ) -> None:
        """Register an asynchronous callback for Socket.IO disconnects."""
        self._socket_disconnect_callbacks.append(callback)

    def register_socket_connect_callback(
        self, callback: Callable[[], Awaitable[None]]
    ) -> None:
        """Register an asynchronous callback for Socket.IO connects and reconnects."""
        self._socket_connect_callbacks.append(callback)

    async def _handle_smart_coop_update(self, data: dict[str, Any]) -> None:
        """Forward a parsed SmartCoop state update from Socket.IO."""
        smart_coop = SmartCoop.from_api(data, self)
        for callback in self._smart_coop_update_callbacks:
            await callback(smart_coop)

    async def _handle_socket_event(self, event: str, data: Any) -> None:
        """Forward Socket.IO events to registered diagnostic callbacks."""
        for callback in self._socket_event_callbacks:
            await callback(event, data)

    async def _handle_socket_disconnect(self) -> None:
        """Notify subscribers after Socket.IO loses its connection."""
        for callback in self._socket_disconnect_callbacks:
            await callback()

    def _require_session(self) -> aiohttp.ClientSession:
        if self._session is None:
            raise RuntimeError("Call login() before requesting devices.")
        return self._session
