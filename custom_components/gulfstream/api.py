"""Async client for the GulfStream / CaptouchWiFi cloud API."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

import aiohttp

from .const import (
    API_URL,
    KEY_MODE,
    REG_SETPOINT_BLOCK_LEN,
    REG_SETPOINT_BLOCK_START,
    USER_AGENT,
)

_LOGGER = logging.getLogger(__name__)

_REQUEST_TIMEOUT = 20
_MAX_RETRIES = 3
_RETRY_BACKOFF = 2.0


class GulfstreamError(Exception):
    """Base error for the Gulfstream API."""


class GulfstreamAuthError(GulfstreamError):
    """Raised when authentication fails (bad username/password)."""


class GulfstreamConnectionError(GulfstreamError):
    """Raised when the API cannot be reached or returns a server error."""


@dataclass
class GulfstreamDevice:
    """A thermostat/heater belonging to the account."""

    key: str
    name: str
    model: str
    online: bool
    state: dict[str, Any] = field(default_factory=dict)


class GulfstreamApi:
    """Minimal async wrapper around POST https://www.captouchwifi.com/icm/api/call."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        username: str,
        password: str,
    ) -> None:
        """Initialise the client with an aiohttp session and credentials."""
        self._session = session
        self._username = username
        self._password = password
        self._token: str | None = None

    async def _request(self, payload: dict[str, Any]) -> dict[str, Any]:
        """POST a single JSON command, retrying transient 5xx errors."""
        last_exc: Exception | None = None
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                async with asyncio.timeout(_REQUEST_TIMEOUT):
                    resp = await self._session.post(
                        API_URL,
                        json=payload,
                        headers={"User-Agent": USER_AGENT},
                    )
                    if resp.status >= 500:
                        raise GulfstreamConnectionError(
                            f"Server returned HTTP {resp.status}"
                        )
                    if resp.status in (401, 403):
                        raise GulfstreamAuthError(f"HTTP {resp.status}")
                    resp.raise_for_status()
                    # The API returns application/json but has been seen to
                    # occasionally mislabel the content type, so don't enforce it.
                    return await resp.json(content_type=None)
            except (GulfstreamConnectionError, aiohttp.ClientError, asyncio.TimeoutError) as err:
                last_exc = err
                if attempt < _MAX_RETRIES:
                    await asyncio.sleep(_RETRY_BACKOFF * attempt)
                    continue
        raise GulfstreamConnectionError(
            f"Request failed after {_MAX_RETRIES} attempts: {last_exc}"
        ) from last_exc

    async def _call(
        self, payload: dict[str, Any], *, _allow_relogin: bool = True
    ) -> dict[str, Any]:
        """Call an authenticated action, logging in / re-authing as needed."""
        action = payload.get("action")
        if action != "login" and self._token is None:
            await self.login()

        body = dict(payload)
        if action != "login":
            body["token"] = self._token

        data = await self._request(body)

        if data.get("result") != "success" and action != "login":
            # The token may have expired; try exactly one fresh login + retry.
            if _allow_relogin:
                _LOGGER.debug("Call %s not successful, re-authenticating", action)
                await self.login()
                return await self._call(payload, _allow_relogin=False)
            raise GulfstreamError(f"Action {action} failed: {data!r}")

        return data

    async def login(self) -> None:
        """Authenticate and cache the session token."""
        data = await self._request(
            {
                "action": "login",
                "username": self._username,
                "password": self._password,
            }
        )
        if data.get("result") != "success" or not data.get("token"):
            raise GulfstreamAuthError("Invalid username or password")
        self._token = data["token"]

    async def async_validate(self) -> list[GulfstreamDevice]:
        """Validate credentials and return the account's devices (for config flow)."""
        await self.login()
        return await self.async_get_devices()

    async def async_get_devices(self) -> list[GulfstreamDevice]:
        """Return the list of devices on the account (without full state)."""
        data = await self._call(
            {
                "action": "getPasDevices",
                "additionalFields": ["MD", "CF", "RMT"],
            }
        )
        devices: list[GulfstreamDevice] = []
        for raw in data.get("devices", []):
            devices.append(
                GulfstreamDevice(
                    key=raw["unique_key"],
                    name=raw.get("name") or raw["unique_key"],
                    model=raw.get("model_name", "Pool Heater"),
                    online=str(raw.get("online", "0")) == "1",
                )
            )
        return devices

    async def async_get_detail(self, key: str) -> dict[str, Any]:
        """Return the full ``currentState`` register map for one device."""
        data = await self._call(
            {"action": "thermostatGetDetail", "thermostatKey": key}
        )
        detail = data.get("detail", {})
        state = dict(detail.get("currentState", {}))
        # Surface a couple of useful top-level fields alongside the registers.
        if "last_online" in detail:
            state["_last_online"] = detail["last_online"]
        return state

    async def async_set_block(
        self, key: str, start_address: int, values: list[int]
    ) -> None:
        """Write a raw register block (``thermostatSetBlock``)."""
        data = await self._call(
            {
                "action": "thermostatSetBlock",
                "thermostatKey": key,
                "startAddress": start_address,
                "length": len(values),
                "data": values,
            }
        )
        if data.get("result") != "success":
            raise GulfstreamError(f"setBlock failed: {data!r}")

    async def async_write_setpoint_and_mode(
        self,
        key: str,
        *,
        setpoint: int,
        spa_setpoint: int,
        mode: int,
    ) -> None:
        """Write the 27..33 block exactly as the mobile app does.

        data = [RSV1(setpoint), RSV2(spa), RSV3, FLT, RSFL, RSWF, MD(mode)]
        The four middle flag registers are always written as 0, matching the app.
        """
        values = [int(setpoint), int(spa_setpoint), 0, 0, 0, 0, int(mode)]
        assert len(values) == REG_SETPOINT_BLOCK_LEN
        await self.async_set_block(key, REG_SETPOINT_BLOCK_START, values)
