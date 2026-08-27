"""Tests for the notiOne API client."""
from datetime import datetime, timezone

import pytest
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMockResponse,
)
from yarl import URL

from custom_components.notione.api import (
    NotiOneApiError,
    NotiOneAuthError,
    NotiOneClient,
)
from custom_components.notione.const import LIST_URL, TOKEN_URL

from homeassistant.helpers.aiohttp_client import async_get_clientsession

BLE_DEVICE = {
    "deviceId": 111222,
    "name": "Samochód",
    "avatar": "https://cdn.notinote.me/avatar/car.png",
    "deviceVersion": "3.0",
    "lastPosition": {
        "latitude": 53.13,
        "longitude": 23.16,
        "gpstime": 1787000000000,
        "accuracy": 12.5,
        "geocodeCity": "Białystok",
        "geocodePlace": "Lipowa",
    },
    "notiOneDetails": {"battery": False, "mac": "AA:BB:CC:DD:EE:FF"},
    "gpsDetails": None,
}

GPS_DEVICE = {
    "deviceId": 333444,
    "name": None,
    "avatar": None,
    "deviceVersion": "gps-1",
    "lastPosition": {
        "latitude": 52.0,
        "longitude": 21.0,
        "gpstime": 1787000500000,
        "accuracy": 5.0,
        "geocodeCity": None,
        "geocodePlace": None,
    },
    "notiOneDetails": None,
    "gpsDetails": {"battery": True, "imei": "356938035643809"},
}


def mock_auth_ok(aioclient_mock):
    aioclient_mock.post(TOKEN_URL, json={"access_token": "token-1"})


async def test_get_devices_returns_parsed_devices(hass, aioclient_mock):
    mock_auth_ok(aioclient_mock)
    aioclient_mock.get(LIST_URL, json={"deviceList": [BLE_DEVICE, GPS_DEVICE]})
    client = NotiOneClient(async_get_clientsession(hass), "user@example.com", "pw")

    devices = await client.async_get_devices()

    assert len(devices) == 2
    car = next(d for d in devices if d.device_id == 111222)
    assert car.name == "Samochód"
    assert car.latitude == 53.13
    assert car.longitude == 23.16
    assert car.accuracy == 12.5
    assert car.gps_time == datetime.fromtimestamp(1787000000, tz=timezone.utc)
    assert car.battery_low is False
    assert car.mac == "AA:BB:CC:DD:EE:FF"
    assert car.avatar_url == "https://cdn.notinote.me/avatar/car.png"
    assert car.city == "Białystok"
    assert car.street == "Lipowa"

    gps = next(d for d in devices if d.device_id == 333444)
    assert gps.name == "333444"
    assert gps.battery_low is True
    assert gps.mac == "356938035643809"
    assert gps.avatar_url is None
    assert gps.city == ""
    assert gps.street == ""


async def test_bad_credentials_raise_auth_error(hass, aioclient_mock):
    aioclient_mock.post(TOKEN_URL, status=400, json={"error": "invalid_grant"})
    client = NotiOneClient(async_get_clientsession(hass), "user@example.com", "bad")

    with pytest.raises(NotiOneAuthError):
        await client.async_get_devices()


async def test_missing_access_token_raises_auth_error(hass, aioclient_mock):
    aioclient_mock.post(TOKEN_URL, json={"unexpected": "shape"})
    client = NotiOneClient(async_get_clientsession(hass), "user@example.com", "pw")

    with pytest.raises(NotiOneAuthError):
        await client.async_get_devices()


async def test_malformed_device_list_raises_api_error(hass, aioclient_mock):
    mock_auth_ok(aioclient_mock)
    aioclient_mock.get(LIST_URL, json={"unexpected": []})
    client = NotiOneClient(async_get_clientsession(hass), "user@example.com", "pw")

    with pytest.raises(NotiOneApiError):
        await client.async_get_devices()


async def test_device_missing_position_raises_api_error(hass, aioclient_mock):
    mock_auth_ok(aioclient_mock)
    broken = dict(BLE_DEVICE, lastPosition=None)
    aioclient_mock.get(LIST_URL, json={"deviceList": [broken]})
    client = NotiOneClient(async_get_clientsession(hass), "user@example.com", "pw")

    with pytest.raises(NotiOneApiError):
        await client.async_get_devices()


async def test_server_error_raises_api_error(hass, aioclient_mock):
    mock_auth_ok(aioclient_mock)
    aioclient_mock.get(LIST_URL, status=500)
    client = NotiOneClient(async_get_clientsession(hass), "user@example.com", "pw")

    with pytest.raises(NotiOneApiError):
        await client.async_get_devices()


async def test_rejected_token_reauthenticates_exactly_once(hass, aioclient_mock):
    mock_auth_ok(aioclient_mock)
    aioclient_mock.get(LIST_URL, status=401)
    client = NotiOneClient(async_get_clientsession(hass), "user@example.com", "pw")

    with pytest.raises(NotiOneAuthError):
        await client.async_get_devices()

    token_calls = [c for c in aioclient_mock.mock_calls if str(c[1]) == TOKEN_URL]
    list_calls = [c for c in aioclient_mock.mock_calls if str(c[1]) == LIST_URL]
    assert len(token_calls) == 2
    assert len(list_calls) == 2


async def test_expired_token_403_reauthenticates_and_recovers(hass, aioclient_mock):
    # The live API rejects an expired token on the device list with 403, not 401.
    mock_auth_ok(aioclient_mock)
    list_responses = [
        AiohttpClientMockResponse("get", URL(LIST_URL), status=403),
        AiohttpClientMockResponse(
            "get", URL(LIST_URL), json={"deviceList": [BLE_DEVICE]}
        ),
    ]

    async def next_list_response(method, url, data):
        return list_responses.pop(0)

    aioclient_mock.get(LIST_URL, side_effect=next_list_response)
    client = NotiOneClient(async_get_clientsession(hass), "user@example.com", "pw")

    devices = await client.async_get_devices()

    assert [d.device_id for d in devices] == [111222]
    token_calls = [c for c in aioclient_mock.mock_calls if str(c[1]) == TOKEN_URL]
    list_calls = [c for c in aioclient_mock.mock_calls if str(c[1]) == LIST_URL]
    assert len(token_calls) == 2
    assert len(list_calls) == 2


async def test_persistent_403_after_reauth_raises_api_error(hass, aioclient_mock):
    # A 403 that survives a fresh login is a server-side policy problem, not bad
    # credentials: raise the retryable API error, never the reauth-flow error.
    mock_auth_ok(aioclient_mock)
    aioclient_mock.get(LIST_URL, status=403)
    client = NotiOneClient(async_get_clientsession(hass), "user@example.com", "pw")

    with pytest.raises(NotiOneApiError) as err:
        await client.async_get_devices()

    assert not isinstance(err.value, NotiOneAuthError)
    token_calls = [c for c in aioclient_mock.mock_calls if str(c[1]) == TOKEN_URL]
    list_calls = [c for c in aioclient_mock.mock_calls if str(c[1]) == LIST_URL]
    assert len(token_calls) == 2
    assert len(list_calls) == 2
