"""Tests for the notiOne config flow."""
from unittest.mock import patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.notione.const import (
    CONF_TRACKED_DEVICES,
    DOMAIN,
    LIST_URL,
    TOKEN_URL,
)

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResultType

from .test_api import BLE_DEVICE, GPS_DEVICE, mock_auth_ok

CREDS = {CONF_USERNAME: "user@example.com", CONF_PASSWORD: "pw"}


def mock_api_ok(aioclient_mock):
    mock_auth_ok(aioclient_mock)
    aioclient_mock.get(LIST_URL, json={"deviceList": [BLE_DEVICE, GPS_DEVICE]})


async def start_user_flow(hass):
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )


async def test_user_flow_creates_entry_with_picked_devices(hass, aioclient_mock):
    mock_api_ok(aioclient_mock)
    result = await start_user_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=CREDS
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "devices"

    with patch(
        "custom_components.notione.async_setup_entry", return_value=True
    ) as setup:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_TRACKED_DEVICES: ["111222"]}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "user@example.com"
    assert result["data"] == CREDS
    assert result["options"] == {CONF_TRACKED_DEVICES: ["111222"]}
    assert len(setup.mock_calls) == 1
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.unique_id == "user@example.com"


async def test_user_flow_bad_credentials_shows_error(hass, aioclient_mock):
    aioclient_mock.post(TOKEN_URL, status=400, json={"error": "invalid_grant"})
    result = await start_user_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=CREDS
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_user_flow_unreachable_api_shows_error(hass, aioclient_mock):
    aioclient_mock.post(TOKEN_URL, exc=OSError("no route"))
    result = await start_user_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=CREDS
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_duplicate_account_is_aborted(hass, aioclient_mock):
    MockConfigEntry(
        domain=DOMAIN, data=CREDS, unique_id="user@example.com"
    ).add_to_hass(hass)
    mock_api_ok(aioclient_mock)
    result = await start_user_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=CREDS
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_options_flow_updates_tracked_devices(hass, aioclient_mock):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=CREDS,
        options={CONF_TRACKED_DEVICES: ["111222"]},
        unique_id="user@example.com",
    )
    entry.add_to_hass(hass)
    mock_api_ok(aioclient_mock)

    with patch("custom_components.notione.async_setup_entry", return_value=True):
        result = await hass.config_entries.options.async_init(entry.entry_id)
        assert result["type"] is FlowResultType.FORM

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={CONF_TRACKED_DEVICES: ["111222", "333444"]},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {CONF_TRACKED_DEVICES: ["111222", "333444"]}


async def test_reauth_flow_updates_password(hass, aioclient_mock):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=CREDS,
        options={CONF_TRACKED_DEVICES: ["111222"]},
        unique_id="user@example.com",
    )
    entry.add_to_hass(hass)
    mock_api_ok(aioclient_mock)

    with patch("custom_components.notione.async_setup_entry", return_value=True):
        result = await entry.start_reauth_flow(hass)
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_PASSWORD: "new-pw"}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_PASSWORD] == "new-pw"
