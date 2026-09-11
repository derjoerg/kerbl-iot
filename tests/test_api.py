"""Tests for Kerbl IoT HTTP and Socket.IO transport."""

import unittest
from typing import Any
from unittest.mock import patch

import aiohttp
import socketio

from kerbl_iot import (
    KerblAuthenticationError,
    KerblConnectionError,
    KerblIOTApi,
    KerblProtocolError,
)


class FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    async def __aenter__(self) -> "FakeResponse":
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def json(self) -> dict[str, Any]:
        return self._payload


class FakeSession:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.headers: dict[str, str] = {}
        self.request_args: list[tuple[str, str, dict[str, Any] | None]] = []
        self.closed = False
        self.errors: list[Exception] = []

    def request(self, method: str, endpoint: str, *, json: dict[str, Any] | None) -> FakeResponse:
        if self.errors:
            raise self.errors.pop(0)
        self.request_args.append((method, endpoint, json))
        return FakeResponse(self.payload)

    async def close(self) -> None:
        self.closed = True


class FakeSocket:
    def __init__(self) -> None:
        self.connected = True
        self.handlers: dict[str, object] = {}
        self.emitted: list[tuple[str, dict[str, object]]] = []
        self.disconnected = False

    def on(self, event: str, handler: object) -> None:
        self.handlers[event] = handler

    async def connect(self, *args: object, **kwargs: object) -> None:
        return None

    async def emit(self, event: str, data: dict[str, object]) -> None:
        self.emitted.append((event, data))

    async def disconnect(self) -> None:
        self.disconnected = True
        self.connected = False


class KerblIOTApiTest(unittest.IsolatedAsyncioTestCase):
    async def test_constructor_and_context_manager(self) -> None:
        with self.assertRaises(ValueError):
            KerblIOTApi("test@example.com", "password", timeout=0)
        api = KerblIOTApi("test@example.com", "password")
        api.login = unittest.mock.AsyncMock()
        api.close = unittest.mock.AsyncMock()
        async with api:
            pass
        api.login.assert_awaited_once()
        api.close.assert_awaited_once()

    async def test_login_and_refresh_update_bearer_token(self) -> None:
        session = FakeSession({"accessToken": "access", "refreshToken": "refresh"})
        api = KerblIOTApi("test@example.com", "password", session=session)  # type: ignore[arg-type]

        with patch("kerbl_iot.api.aiohttp.ClientSession") as client_session:
            await api.login()

        client_session.assert_not_called()
        self.assertEqual(session.headers["Authorization"], "Bearer access")
        self.assertEqual(
            session.request_args[0][1], "https://app.kerbl-iot.com/api/v0.1/auth/sign-in"
        )
        await api.refresh_token()
        self.assertEqual(
            session.request_args[1][1], "https://app.kerbl-iot.com/api/v0.1/auth/refresh"
        )
        await api.close()

    async def test_login_creates_and_closes_owned_session(self) -> None:
        session = FakeSession({"accessToken": "access", "refreshToken": "refresh"})
        api = KerblIOTApi("test@example.com", "password")

        with patch("kerbl_iot.api.aiohttp.ClientSession", return_value=session) as client_session:
            await api.login()
            client_session.assert_called_once()

        await api.close()
        self.assertTrue(session.closed)

    async def test_login_closes_owned_session_when_request_fails(self) -> None:
        session = FakeSession({})
        session.errors.append(aiohttp.ClientConnectionError())
        api = KerblIOTApi("test@example.com", "password")

        with patch("kerbl_iot.api.aiohttp.ClientSession", return_value=session):
            with self.assertRaises(KerblConnectionError):
                await api.login()

        self.assertTrue(session.closed)

    async def test_login_requires_both_tokens(self) -> None:
        session = FakeSession({"accessToken": "access"})
        api = KerblIOTApi("test@example.com", "password", session=session)  # type: ignore[arg-type]

        with self.assertRaises(KerblAuthenticationError):
            await api.login()

        self.assertFalse(session.closed)

    async def test_tokens_can_be_exported_and_restored(self) -> None:
        session = FakeSession({"accessToken": "access", "refreshToken": "refresh"})
        api = KerblIOTApi("test@example.com", "password", session=session)  # type: ignore[arg-type]
        await api.login()

        tokens = api.get_tokens()
        restored_session = FakeSession({"accessToken": "new-access", "refreshToken": "new-refresh"})
        restored_api = KerblIOTApi(
            "test@example.com",
            "password",
            session=restored_session,  # type: ignore[arg-type]
        )
        restored_api.restore_tokens(*tokens)

        self.assertEqual(tokens, ("access", "refresh"))
        self.assertEqual(restored_session.headers["Authorization"], "Bearer access")
        await restored_api.refresh_token()
        self.assertEqual(restored_api.get_tokens(), ("new-access", "new-refresh"))

    async def test_tokens_can_be_restored_without_session_injection(self) -> None:
        session = FakeSession({"accessToken": "new-access", "refreshToken": "new-refresh"})
        api = KerblIOTApi("test@example.com", "password")

        with patch("kerbl_iot.api.aiohttp.ClientSession", return_value=session) as client_session:
            api.restore_tokens("access", "refresh")

        client_session.assert_called_once()
        self.assertEqual(session.headers["Authorization"], "Bearer access")
        self.assertEqual(session.request_args, [])
        await api.close()
        self.assertTrue(session.closed)

    def test_get_tokens_requires_authentication(self) -> None:
        api = KerblIOTApi("test@example.com", "password")
        with self.assertRaises(KerblAuthenticationError):
            api.get_tokens()

    async def test_refresh_and_request_error_paths(self) -> None:
        api = KerblIOTApi("test@example.com", "password")
        session = FakeSession({})
        api._session = session  # type: ignore[assignment]
        with self.assertRaises(KerblAuthenticationError):
            await api.refresh_token()
        api._access_token = "access"
        api._refresh_token = "refresh"
        session.errors.append(ValueError("bad json"))
        with self.assertRaises(KerblProtocolError):
            await api.refresh_token()

        api._session = FakeSession({})  # type: ignore[assignment]
        api._access_token = "access"
        api._refresh_token = "refresh"
        api.refresh_token = unittest.mock.AsyncMock()
        api._session.errors.extend([aiohttp.ClientResponseError(None, (), status=401)])
        await api._request_json("GET", "device")
        api.refresh_token.assert_awaited_once()

    async def test_request_wraps_non_unauthorized_http_errors(self) -> None:
        api = KerblIOTApi("test@example.com", "password")
        session = FakeSession({})
        api._session = session  # type: ignore[assignment]
        session.errors.append(aiohttp.ClientResponseError(None, (), status=503))

        with self.assertRaises(KerblConnectionError):
            await api._request_json("GET", "device")

    async def test_refresh_keeps_session_and_preserves_error_category(self) -> None:
        session = FakeSession({})
        api = KerblIOTApi("test@example.com", "password")
        api._session = session  # type: ignore[assignment]
        api._access_token = "access"
        api._refresh_token = "refresh"

        session.errors.append(aiohttp.ClientConnectionError())
        with self.assertRaises(KerblConnectionError):
            await api.refresh_token()
        self.assertIs(api._session, session)
        self.assertFalse(session.closed)

        session.errors.append(ValueError("bad json"))
        with self.assertRaises(KerblProtocolError):
            await api.refresh_token()
        self.assertIs(api._session, session)
        self.assertFalse(session.closed)

        session.errors.append(aiohttp.ClientResponseError(None, (), status=401))
        with self.assertRaises(KerblAuthenticationError):
            await api.refresh_token()
        self.assertIs(api._session, session)
        self.assertFalse(session.closed)

    async def test_protocol_and_unauthorized_errors(self) -> None:
        api = KerblIOTApi("test@example.com", "password")
        session = FakeSession({})
        api._session = session  # type: ignore[assignment]
        session.errors.append(ValueError("bad json"))
        with self.assertRaises(Exception):
            await api._request_json("GET", "device")
        session.errors.append(aiohttp.ClientResponseError(None, (), status=401))
        with self.assertRaises(KerblAuthenticationError):
            await api._request_json("GET", "device", refresh_on_unauthorized=False)

    async def test_authentication_guards(self) -> None:
        api = KerblIOTApi("test@example.com", "password")
        with self.assertRaises(RuntimeError):
            api._require_session()
        api._session = FakeSession({})  # type: ignore[assignment]
        with self.assertRaises(KerblAuthenticationError):
            api._set_authentication({"refreshToken": "refresh"})
        api._access_token = "access"
        api._refresh_token = "refresh"
        api._request_json = unittest.mock.AsyncMock(side_effect=KerblAuthenticationError())
        with self.assertRaises(KerblAuthenticationError):
            await api.refresh_token()

    async def test_reads_devices_logs_and_sends_command(self) -> None:
        session = FakeSession(
            {"smartCoop": [{"id": "coop-1", "userId": "user-1", "isOnline": True}]}
        )
        api = KerblIOTApi("test@example.com", "password")
        api._session = session  # type: ignore[assignment]

        coops = await api.get_smart_coops()
        self.assertEqual(coops[0].id, "coop-1")
        session.payload = {"logs": []}
        self.assertEqual(await api.get_smart_coop_logs("coop-1"), [])
        session.payload = {"success": True, "commandCount": 1}
        result = await api._press_light("coop-1")

        self.assertTrue(result.success)
        self.assertEqual(
            session.request_args[-1],
            ("PATCH", "device/smart-coop/coop-1/command/lightControl", {"value": 1}),
        )

    async def test_request_wraps_connection_errors(self) -> None:
        api = KerblIOTApi("test@example.com", "password")
        session = FakeSession({})
        session.request = lambda *args, **kwargs: (_ for _ in ()).throw(  # type: ignore[method-assign]
            aiohttp.ClientConnectionError()
        )
        api._session = session  # type: ignore[assignment]

        with self.assertRaises(KerblConnectionError):
            await api.get_smart_coops()

    async def test_command_variants_and_empty_acknowledgement(self) -> None:
        session = FakeSession({"success": True, "commandCount": 1})
        api = KerblIOTApi("test@example.com", "password")
        api._session = session  # type: ignore[assignment]
        await api._press_feeder("coop-1")
        await api._press_door("coop-1")
        await api._acknowledge_errors("coop-1", [256])
        with self.assertRaises(ValueError):
            await api._acknowledge_errors("coop-1", [])

    async def test_socket_rejoins_after_reconnect_and_closes(self) -> None:
        session = FakeSession(
            {"smartCoop": [{"id": "coop-1", "userId": "user-1", "isOnline": True}]}
        )
        session.headers["Authorization"] = "Bearer access"
        api = KerblIOTApi("test@example.com", "password")
        api._session = session  # type: ignore[assignment]
        smart_coop = (await api.get_smart_coops())[0]
        socket = FakeSocket()

        with patch("kerbl_iot.api.socketio.AsyncClient", return_value=socket):
            await api.connect_websocket([smart_coop])

        await api._handle_socket_connect()
        await api.close()

        self.assertEqual(socket.emitted[0][0], "join_room")
        self.assertEqual(socket.emitted[1][0], "join_room")
        self.assertEqual(socket.emitted[-1][0], "leave_room")
        self.assertTrue(socket.disconnected)

    async def test_socket_reconnection_options_are_forwarded(self) -> None:
        session = FakeSession({})
        session.headers["Authorization"] = "Bearer access"
        api = KerblIOTApi("test@example.com", "password")
        api._session = session  # type: ignore[assignment]
        socket = FakeSocket()

        with patch("kerbl_iot.api.socketio.AsyncClient", return_value=socket) as client:
            await api.connect_websocket(
                [type("Coop", (), {"id": "coop-1", "user_id": "user-1"})()],
                reconnection_attempts=4,
                reconnection_delay=2.5,
            )

        client.assert_called_once_with(
            reconnection=True,
            reconnection_attempts=4,
            reconnection_delay=2.5,
            logger=False,
            engineio_logger=False,
        )

    async def test_socket_reconnection_options_reject_negative_values(self) -> None:
        api = KerblIOTApi("test@example.com", "password")
        coop = type("Coop", (), {"id": "coop-1", "user_id": "user-1"})()

        with self.assertRaises(ValueError):
            await api.connect_websocket([coop], reconnection_attempts=-1)
        with self.assertRaises(ValueError):
            await api.connect_websocket([coop], reconnection_delay=-1)

    async def test_socket_skip_failure_and_callbacks(self) -> None:
        api = KerblIOTApi("test@example.com", "password")
        await api.connect_websocket([])
        api._socket = FakeSocket()  # type: ignore[assignment]
        await api.connect_websocket([])
        api._socket = None
        session = FakeSession({})
        session.headers["Authorization"] = "Bearer access"
        api._session = session  # type: ignore[assignment]
        socket = FakeSocket()
        socket.connect = unittest.mock.AsyncMock(side_effect=socketio.exceptions.ConnectionError())
        coop = type("Coop", (), {"id": "coop-1", "user_id": "user-1"})()
        with patch("kerbl_iot.api.socketio.AsyncClient", return_value=socket):
            with self.assertRaises(KerblConnectionError):
                await api.connect_websocket([coop])
        callback = unittest.mock.AsyncMock()
        event_callback = unittest.mock.AsyncMock()
        disconnect_callback = unittest.mock.AsyncMock()
        connect_callback = unittest.mock.AsyncMock()
        api.register_smart_coop_update_callback(callback)
        api.register_socket_event_callback(event_callback)
        api.register_socket_disconnect_callback(disconnect_callback)
        api.register_socket_connect_callback(connect_callback)
        await api._handle_smart_coop_update({"id": "coop-1", "userId": "user-1", "isOnline": True})
        await api._handle_socket_event("pong", None)
        await api._handle_socket_disconnect()
        await api._handle_socket_connect()
        callback.assert_awaited_once()
        event_callback.assert_awaited_once_with("pong", None)
        disconnect_callback.assert_awaited_once()
        connect_callback.assert_awaited_once()
