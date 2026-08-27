"""Tests for notiOne entry setup and tracker entities."""
from datetime import timedelta

from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.notione.const import (
    CONF_TRACKED_DEVICES,
    DOMAIN,
    LIST_URL,
)

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_USERNAME,
    STATE_UNAVAILABLE,
)
from homeassistant.util import dt as dt_util

from .test_api import BLE_DEVICE, GPS_DEVICE, mock_auth_ok

CREDS = {CONF_USERNAME: "user@example.com", CONF_PASSWORD: "pw"}


def make_entry(tracked=("111222",)):
    return MockConfigEntry(
        domain=DOMAIN,
        data=CREDS,
        options={CONF_TRACKED_DEVICES: list(tracked)},
        unique_id="user@example.com",
    )


async def setup_entry(hass, aioclient_mock, entry, devices):
    mock_auth_ok(aioclient_mock)
    aioclient_mock.get(LIST_URL, json={"deviceList": devices})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_tracked_device_creates_tracker_entity(hass, aioclient_mock):
    entry = make_entry()
    await setup_entry(hass, aioclient_mock, entry, [BLE_DEVICE, GPS_DEVICE])

    assert entry.state is ConfigEntryState.LOADED
    state = hass.states.get("device_tracker.samochod")
    assert state is not None
    assert state.attributes["latitude"] == 53.13
    assert state.attributes["longitude"] == 23.16
    assert state.attributes["gps_accuracy"] == 12.5
    assert state.attributes["beaconid"] == 111222
    assert state.attributes["battery_status"] == "high"
    assert state.attributes["deviceVersion"] == "3.0"
    assert state.attributes["location"] == "Lipowa, Białystok"
    assert (
        state.attributes["entity_picture"]
        == "https://cdn.notinote.me/avatar/car.png"
    )


async def test_untracked_device_gets_no_entity(hass, aioclient_mock):
    entry = make_entry(tracked=("111222",))
    await setup_entry(hass, aioclient_mock, entry, [BLE_DEVICE, GPS_DEVICE])

    tracker_states = [
        s for s in hass.states.async_all("device_tracker")
        if s.entity_id.startswith("device_tracker.")
    ]
    assert [s.entity_id for s in tracker_states] == ["device_tracker.samochod"]


async def test_device_dropped_from_response_becomes_unavailable(
    hass, aioclient_mock
):
    entry = make_entry()
    await setup_entry(hass, aioclient_mock, entry, [BLE_DEVICE])
    assert hass.states.get("device_tracker.samochod").state != STATE_UNAVAILABLE

    aioclient_mock.clear_requests()
    mock_auth_ok(aioclient_mock)
    aioclient_mock.get(LIST_URL, json={"deviceList": []})
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=301))
    await hass.async_block_till_done()

    assert hass.states.get("device_tracker.samochod").state == STATE_UNAVAILABLE


async def test_api_error_marks_entities_unavailable(hass, aioclient_mock):
    entry = make_entry()
    await setup_entry(hass, aioclient_mock, entry, [BLE_DEVICE])

    aioclient_mock.clear_requests()
    mock_auth_ok(aioclient_mock)
    aioclient_mock.get(LIST_URL, status=500)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=301))
    await hass.async_block_till_done()

    assert hass.states.get("device_tracker.samochod").state == STATE_UNAVAILABLE


async def test_rejected_credentials_start_reauth(hass, aioclient_mock):
    from custom_components.notione.const import TOKEN_URL

    aioclient_mock.post(TOKEN_URL, status=400, json={"error": "invalid_grant"})
    entry = make_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert any(f["context"].get("source") == "reauth" for f in flows)


async def test_unload_entry(hass, aioclient_mock):
    entry = make_entry()
    await setup_entry(hass, aioclient_mock, entry, [BLE_DEVICE])

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert hass.states.get("device_tracker.samochod").state == STATE_UNAVAILABLE
