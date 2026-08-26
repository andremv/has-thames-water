"""Sensor platform for Thames Water."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN


@dataclass(frozen=True, kw_only=True)
class ThamesWaterSensorDescription(SensorEntityDescription):
    """Description of a Thames Water sensor."""

    key: str
    unit: str
    value_fn: Any


SENSOR_DESCRIPTIONS: tuple[ThamesWaterSensorDescription, ...] = (
    ThamesWaterSensorDescription(
        key="meter_reading",
        name="Water meter reading",
        unit=UnitOfVolume.CUBIC_METERS,
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=3,
        value_fn=lambda d: d["latest_read"] / 1000 if d.get("latest_read") else None,
    ),
    ThamesWaterSensorDescription(
        key="usage_latest_day",
        name="Water usage latest day",
        unit=UnitOfVolume.LITERS,
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda d: d.get("latest_day_usage"),
    ),
    ThamesWaterSensorDescription(
        key="usage_latest_hour",
        name="Water usage latest hour",
        unit=UnitOfVolume.LITERS,
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda d: d.get("latest_hour_usage"),
    ),
    ThamesWaterSensorDescription(
        key="usage_last_30_days",
        name="Water usage last 30 days",
        unit=UnitOfVolume.LITERS,
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda d: d.get("last_30d_usage"),
    ),
    ThamesWaterSensorDescription(
        key="average_daily_usage",
        name="Water usage daily average",
        unit=UnitOfVolume.LITERS,
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda d: d.get("average_daily_usage"),
    ),
    ThamesWaterSensorDescription(
        key="usage_billing_period",
        name="Water usage billing period",
        unit=UnitOfVolume.LITERS,
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda d: d.get("actual_usage"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Thames Water sensors."""
    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        ThamesWaterSensor(coordinator, entry, description)
        for description in SENSOR_DESCRIPTIONS
    )


class ThamesWaterSensor(CoordinatorEntity, SensorEntity):
    """A Thames Water usage sensor."""

    entity_description: ThamesWaterSensorDescription

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        entry: ConfigEntry,
        description: ThamesWaterSensorDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Thames Water",
            "manufacturer": "Thames Water",
            "model": "Smart water meter",
        }

    @property
    def native_value(self) -> float | None:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        data = self.coordinator.data or {}
        attrs: dict[str, Any] = {
            "meter_serial_number": (
                data.get("meters", [None])[0] if data.get("meters") else None
            ),
            "account_number": data.get("account_number"),
            "premise_id": data.get("premise_id"),
            "premise_address": data.get("premise_address"),
        }
        latest = data.get("latest_read_dt")
        if isinstance(latest, datetime):
            attrs["latest_reading_time"] = latest.isoformat()
        attrs["is_estimated"] = data.get("is_estimated")
        return attrs
