"""Device tracker entities for notiOne trackers."""
from __future__ import annotations

from homeassistant.components.device_tracker import TrackerEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import NotiOneConfigEntry, NotiOneCoordinator
from .const import CONF_TRACKED_DEVICES, DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NotiOneConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create one tracker entity per tracked device."""
    coordinator = entry.runtime_data
    tracked = entry.options.get(CONF_TRACKED_DEVICES, [])
    async_add_entities(
        NotiOneTrackerEntity(coordinator, device_id) for device_id in tracked
    )


class NotiOneTrackerEntity(CoordinatorEntity[NotiOneCoordinator], TrackerEntity):
    """Position of one notiOne tracker."""

    _attr_icon = "mdi:bluetooth-connect"

    def __init__(self, coordinator: NotiOneCoordinator, device_id: str) -> None:
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_unique_id = device_id
        device = coordinator.data.get(device_id)
        self._attr_name = device.name if device else device_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=self._attr_name,
            manufacturer="notiOne",
            model=device.device_version if device else None,
        )

    @property
    def _device(self):
        return self.coordinator.data.get(self._device_id)

    @property
    def available(self) -> bool:
        return super().available and self._device is not None

    @property
    def latitude(self) -> float | None:
        device = self._device
        return device.latitude if device else None

    @property
    def longitude(self) -> float | None:
        device = self._device
        return device.longitude if device else None

    @property
    def location_accuracy(self) -> float:
        device = self._device
        return device.accuracy if device else 0

    @property
    def entity_picture(self) -> str | None:
        device = self._device
        return device.avatar_url if device else None

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        device = self._device
        if device is None:
            return {}
        return {
            "gpstime": device.gps_time,
            "beaconid": device.device_id,
            "location": ", ".join(part for part in (device.street, device.city) if part),
            "battery_status": "low" if device.battery_low else "high",
            "deviceVersion": device.device_version,
        }
