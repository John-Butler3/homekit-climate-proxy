"""Standalone fan entity for the climate's fan speed."""

from __future__ import annotations

from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.components.climate import HVACMode
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
)

from . import ProxyConfigEntry, ProxyData
from .const import TARGET_AUTO
from .entity import ProxyEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ProxyConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    if entry.runtime_data.create_fan:
        async_add_entities([ProxyFan(entry.runtime_data)])


class ProxyFan(ProxyEntity, FanEntity):
    """The climate's fan as a HomeKit Fan accessory (speed slider + auto preset)."""

    _attr_supported_features = (
        FanEntityFeature.SET_SPEED | FanEntityFeature.TURN_ON | FanEntityFeature.TURN_OFF
    )
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(self, data: ProxyData) -> None:
        super().__init__(data, "fan")

    @property
    def supported_features(self) -> FanEntityFeature:
        features = FanEntityFeature.SET_SPEED | FanEntityFeature.TURN_ON | FanEntityFeature.TURN_OFF
        if TARGET_AUTO in self.fan_map.targets:
            features |= FanEntityFeature.PRESET_MODE
        return features

    @property
    def preset_modes(self) -> list[str] | None:
        return [TARGET_AUTO] if TARGET_AUTO in self.fan_map.targets else None

    @property
    def preset_mode(self) -> str | None:
        return TARGET_AUTO if self.fan_map.to_target(self.source_fan_mode) == TARGET_AUTO else None

    @property
    def speed_count(self) -> int:
        return max(1, len(self.fan_map.speeds))

    @property
    def is_on(self) -> bool:
        source = self.source
        return source is not None and source.state not in (HVACMode.OFF, "unavailable", "unknown")

    @property
    def percentage(self) -> int | None:
        target = self.fan_map.to_target(self.source_fan_mode)
        speeds = self.fan_map.speeds
        if target is None or target not in speeds:
            return None
        return ordered_list_item_to_percentage(speeds, target)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"source_fan_mode": self.source_fan_mode, "climate_entity_id": self._data.climate_entity_id}

    async def async_set_percentage(self, percentage: int) -> None:
        if percentage == 0:
            await self.async_turn_off()
            return
        speeds = self.fan_map.speeds
        if not speeds:
            return
        target = percentage_to_ordered_list_item(speeds, percentage)
        await self._ensure_climate_on()
        await self.async_call_source("set_fan_mode", fan_mode=self.fan_map.to_source(target))

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        source_mode = self.fan_map.to_source(preset_mode)
        if source_mode is None:
            return
        await self._ensure_climate_on()
        await self.async_call_source("set_fan_mode", fan_mode=source_mode)

    async def async_turn_on(
        self, percentage: int | None = None, preset_mode: str | None = None, **kwargs: Any
    ) -> None:
        if preset_mode:
            await self.async_set_preset_mode(preset_mode)
        elif percentage:
            await self.async_set_percentage(percentage)
        else:
            await self._ensure_climate_on()

    async def async_turn_off(self, **kwargs: Any) -> None:
        if self._data.fan_off_turns_off_climate:
            await self.async_call_source("set_hvac_mode", hvac_mode=HVACMode.OFF)

    async def _ensure_climate_on(self) -> None:
        source = self.source
        if source is not None and source.state == HVACMode.OFF:
            await self.async_call_source("turn_on")
