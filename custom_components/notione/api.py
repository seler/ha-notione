"""Async client for the notiOne cloud API."""
from __future__ import annotations

from base64 import b64encode
from dataclasses import dataclass
from datetime import datetime, timezone

import aiohttp

from .const import (
    LIST_URL,
    OAUTH_CLIENT_ID,
    OAUTH_CLIENT_SECRET,
    OAUTH_SCOPE,
    REQUEST_TIMEOUT,
    TOKEN_URL,
    USER_AGENT,
)


class NotiOneError(Exception):
    """Base error for notiOne API problems."""


class NotiOneAuthError(NotiOneError):
    """The credentials or the access token were rejected."""


class NotiOneApiError(NotiOneError):
    """The API was unreachable or returned an unexpected response."""


@dataclass(frozen=True)
class NotiOneDevice:
    """One tracker as reported by the device list endpoint."""

    device_id: int
    name: str
    latitude: float
    longitude: float
    accuracy: float
    gps_time: datetime
    battery_low: bool
    mac: str
    device_version: str | None
    avatar_url: str | None
    city: str
    street: str


class NotiOneClient:
    """Authenticates against notiOne and fetches tracker positions."""

    def __init__(
        self, session: aiohttp.ClientSession, username: str, password: str
    ) -> None:
        self._session = session
        self._username = username
        self._password = password
        self._access_token: str | None = None
        self._timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)

    async def async_authenticate(self) -> None:
        """Fetch and cache a fresh access token."""
        data = {
            "grant_type": "password",
            "username": self._username,
            "password": self._password,
            "scope": OAUTH_SCOPE,
        }
        try:
            basic = b64encode(
                f"{OAUTH_CLIENT_ID}:{OAUTH_CLIENT_SECRET}".encode()
            ).decode()
            response = await self._session.post(
                TOKEN_URL,
                data=data,
                headers={
                    "Authorization": f"Basic {basic}",
                    "User-Agent": USER_AGENT,
                },
                timeout=self._timeout,
                allow_redirects=False,
            )
        except (aiohttp.ClientError, TimeoutError, OSError) as err:
            raise NotiOneApiError(f"Token request failed: {err}") from err
        if response.status in (400, 401, 403):
            raise NotiOneAuthError(f"Credentials rejected (HTTP {response.status})")
        if response.status != 200:
            raise NotiOneApiError(f"Token endpoint returned HTTP {response.status}")
        try:
            payload = await response.json(content_type=None)
        except ValueError as err:
            raise NotiOneApiError("Token response is not JSON") from err
        token = payload.get("access_token") if isinstance(payload, dict) else None
        if not token:
            raise NotiOneAuthError("Token response holds no access_token")
        self._access_token = token

    async def async_get_devices(self) -> list[NotiOneDevice]:
        """Return all trackers, re-authenticating once on a rejected token."""
        if self._access_token is None:
            await self.async_authenticate()
        response = await self._request_device_list()
        if response.status == 401:
            await self.async_authenticate()
            response = await self._request_device_list()
            if response.status == 401:
                raise NotiOneAuthError("Access token rejected after re-auth")
        if response.status != 200:
            raise NotiOneApiError(f"Device list returned HTTP {response.status}")
        try:
            payload = await response.json(content_type=None)
        except ValueError as err:
            raise NotiOneApiError("Device list response is not JSON") from err
        if not isinstance(payload, dict) or not isinstance(
            payload.get("deviceList"), list
        ):
            raise NotiOneApiError("Device list response misses deviceList")
        return [_parse_device(raw) for raw in payload["deviceList"]]

    async def _request_device_list(self) -> aiohttp.ClientResponse:
        try:
            return await self._session.get(
                LIST_URL,
                headers={
                    "Authorization": f"Bearer {self._access_token}",
                    "User-Agent": USER_AGENT,
                },
                timeout=self._timeout,
            )
        except (aiohttp.ClientError, TimeoutError, OSError) as err:
            raise NotiOneApiError(f"Device list request failed: {err}") from err


def _parse_device(raw: object) -> NotiOneDevice:
    try:
        position = raw["lastPosition"]
        details = raw["notiOneDetails"]
        if details is not None:
            battery_low = bool(details["battery"])
            mac = str(details["mac"])
        else:
            battery_low = bool(raw["gpsDetails"]["battery"])
            mac = str(raw["gpsDetails"]["imei"])
        avatar = raw.get("avatar")
        return NotiOneDevice(
            device_id=int(raw["deviceId"]),
            name=str(raw["name"] or raw["deviceId"]),
            latitude=float(position["latitude"]),
            longitude=float(position["longitude"]),
            accuracy=float(position["accuracy"]),
            gps_time=datetime.fromtimestamp(
                position["gpstime"] / 1000.0, tz=timezone.utc
            ),
            battery_low=battery_low,
            mac=mac,
            device_version=raw.get("deviceVersion"),
            avatar_url=avatar if avatar and str(avatar).startswith("http") else None,
            city=position.get("geocodeCity") or "",
            street=position.get("geocodePlace") or "",
        )
    except (KeyError, TypeError, ValueError) as err:
        raise NotiOneApiError(f"Malformed device entry: {err}") from err
