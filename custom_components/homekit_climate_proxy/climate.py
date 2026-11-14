"""Proxy climate entity with HomeKit-friendly fan modes."""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ATTR_CURRENT_HUMIDITY,
    ATTR_CURRENT_TEMPERATURE,
    ATTR_HUMIDITY,
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODE,
    ATTR_HVAC_MODES,
    ATTR_MAX_HUMIDITY,
    ATTR_MAX_TEMP,
    ATTR_MIN_HUMIDITY,
    ATTR_MIN_TEMP,
    ATTR_PRESET_MODE,
    ATTR_PRESET_MODES,
    ATTR_SWING_MODE,
    ATTR_SWING_MODES,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    ATTR_TARGET_TEMP_STEP,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_SUPPORTED_FEATURES, ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ProxyConfigEntry, ProxyData
from .const import AUTO_DRY, AUTO_FAN_ONLY, AUTO_HEAT_COOL, AUTO_HIDDEN, DOMAIN
from .entity import ProxyEntity

# Features the proxy can forward one-to-one.
_FORWARDED = (
    ClimateEntityFeature.TARGET_TEMPERATURE
    | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
    | ClimateEntityFeature.TARGET_HUMIDITY
    | ClimateEntityFeature.PRESET_MODE
    | ClimateEntityFeature.SWING_MODE
    | ClimateEntityFeature.TURN_ON
    | ClimateEntityFeature.TURN_OFF
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ProxyConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([ProxyClimate(entry.runtime_data)])


class ProxyClimate(ProxyEntity, ClimateEntity):
    """Mirror of the source climate entity, fan modes translated."""

    _attr_name = None  # takes the device name
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(self, data: ProxyData) -> None:
        super().__init__(data, "climate")

    # ---------------------------------------------------------------- state

    @property
    def temperature_unit(self) -> str:
        return self.hass.config.units.temperature_unit

    @property
    def supported_features(self) -> ClimateEntityFeature:
        source_features = ClimateEntityFeature(int(self.source_attr(ATTR_SUPPORTED_FEATURES, 0) or 0))
        features = source_features & _FORWARDED
        # Always offer on/off: the HomeKit Bridge toggles the thermostat with them.
        features |= ClimateEntityFeature.TURN_ON | ClimateEntityFeature.TURN_OFF
        if source_features & ClimateEntityFeature.FAN_MODE and self.fan_map.targets:
            features |= ClimateEntityFeature.FAN_MODE
        return features

    @property
    def _auto_target(self) -> HVACMode | None:
        """The source mode behind HomeKit's Auto, or None when Auto is hidden / real."""
        if self._data.auto_mode == AUTO_FAN_ONLY:
            return HVACMode.FAN_ONLY
        if self._data.auto_mode == AUTO_DRY:
            return HVACMode.DRY
        return None

    @property
    def hvac_modes(self) -> list[HVACMode]:
        source_modes: list[HVACMode] = []
        for mode in self.source_attr(ATTR_HVAC_MODES) or []:
            try:
                source_modes.append(HVACMode(mode))
            except ValueError:
                continue
        modes = [m for m in source_modes if m not in self._data.hide_hvac_modes]
        auto_target = self._auto_target
        if auto_target is not None:
            # HomeKit's Auto stands in for fan only / dry: offer heat_cool
            # whenever the source has that mode, even if it has no real auto.
            if auto_target in source_modes and HVACMode.HEAT_COOL not in modes:
                modes.append(HVACMode.HEAT_COOL)
            if auto_target not in source_modes and HVACMode.HEAT_COOL in modes:
                modes.remove(HVACMode.HEAT_COOL)
        elif self._data.auto_mode == AUTO_HIDDEN and HVACMode.HEAT_COOL in modes:
            modes.remove(HVACMode.HEAT_COOL)
        if HVACMode.OFF not in modes:
            modes.append(HVACMode.OFF)
        return modes

    @property
    def hvac_mode(self) -> HVACMode | None:
        source = self.source
        if source is None:
            return None
        try:
            mode = HVACMode(source.state)
        except ValueError:
            return None
        auto_target = self._auto_target
        if auto_target is not None and mode == auto_target:
            return HVACMode.HEAT_COOL
        visible = self.hvac_modes
        # With Auto standing in for fan only / dry, the source's real heat_cool
        # must not be reported as heat_cool either.
        misleading = auto_target is not None and mode == HVACMode.HEAT_COOL
        if mode != HVACMode.OFF and (misleading or mode in self._data.hide_hvac_modes or mode not in visible):
            # Report the closest mode HomeKit was offered, so the thermostat
            # never shows a state it cannot select.
            for candidate in (HVACMode.COOL, HVACMode.HEAT, HVACMode.HEAT_COOL, HVACMode.AUTO):
                if candidate in visible and not (misleading and candidate == HVACMode.HEAT_COOL):
                    return candidate
        return mode

    @property
    def hvac_action(self) -> HVACAction | None:
        action = self.source_attr(ATTR_HVAC_ACTION)
        try:
            return HVACAction(action) if action else None
        except ValueError:
            return None

    @property
    def current_temperature(self) -> float | None:
        return self.source_attr(ATTR_CURRENT_TEMPERATURE)

    @property
    def target_temperature(self) -> float | None:
        return self.source_attr(ATTR_TEMPERATURE)

    @property
    def target_temperature_high(self) -> float | None:
        return self.source_attr(ATTR_TARGET_TEMP_HIGH)

    @property
    def target_temperature_low(self) -> float | None:
        return self.source_attr(ATTR_TARGET_TEMP_LOW)

    @property
    def target_temperature_step(self) -> float | None:
        return self.source_attr(ATTR_TARGET_TEMP_STEP)

    @property
    def min_temp(self) -> float:
        value = self.source_attr(ATTR_MIN_TEMP)
        return float(value) if value is not None else super().min_temp

    @property
    def max_temp(self) -> float:
        value = self.source_attr(ATTR_MAX_TEMP)
        return float(value) if value is not None else super().max_temp

    @property
    def current_humidity(self) -> float | None:
        return self.source_attr(ATTR_CURRENT_HUMIDITY)

    @property
    def target_humidity(self) -> float | None:
        return self.source_attr(ATTR_HUMIDITY)

    @property
    def min_humidity(self) -> float:
        value = self.source_attr(ATTR_MIN_HUMIDITY)
        return float(value) if value is not None else super().min_humidity

    @property
    def max_humidity(self) -> float:
        value = self.source_attr(ATTR_MAX_HUMIDITY)
        return float(value) if value is not None else super().max_humidity

    @property
    def preset_modes(self) -> list[str] | None:
        return self.source_attr(ATTR_PRESET_MODES)

    @property
    def preset_mode(self) -> str | None:
        return self.source_attr(ATTR_PRESET_MODE)

    @property
    def swing_modes(self) -> list[str] | None:
        return self.source_attr(ATTR_SWING_MODES)

    @property
    def swing_mode(self) -> str | None:
        return self.source_attr(ATTR_SWING_MODE)

    @property
    def fan_modes(self) -> list[str] | None:
        targets = self.fan_map.targets
        return targets or None

    @property
    def fan_mode(self) -> str | None:
        return self.fan_map.to_target(self.source_fan_mode)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "source_entity_id": self._data.climate_entity_id,
            "source_fan_mode": self.source_fan_mode,
            "fan_mode_mapping": self.fan_map.source_to_target,
        }

    # -------------------------------------------------------------- commands

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        source_mode = self.fan_map.to_source(fan_mode)
        if source_mode is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="unknown_fan_mode",
                translation_placeholders={"mode": fan_mode},
            )
        await self.async_call_source("set_fan_mode", fan_mode=source_mode)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        auto_target = self._auto_target
        if hvac_mode == HVACMode.HEAT_COOL and auto_target is not None:
            hvac_mode = auto_target
        await self.async_call_source("set_hvac_mode", hvac_mode=hvac_mode)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        data = {k: v for k, v in kwargs.items() if k in (ATTR_TEMPERATURE, ATTR_TARGET_TEMP_HIGH, ATTR_TARGET_TEMP_LOW, ATTR_HVAC_MODE)}
        auto_target = self._auto_target
        if data.get(ATTR_HVAC_MODE) == HVACMode.HEAT_COOL and auto_target is not None:
            data[ATTR_HVAC_MODE] = auto_target
        await self.async_call_source("set_temperature", **data)

    async def async_set_humidity(self, humidity: int) -> None:
        await self.async_call_source("set_humidity", humidity=humidity)

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        await self.async_call_source("set_swing_mode", swing_mode=swing_mode)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        await self.async_call_source("set_preset_mode", preset_mode=preset_mode)

    async def async_turn_on(self) -> None:
        source_features = ClimateEntityFeature(int(self.source_attr(ATTR_SUPPORTED_FEATURES, 0) or 0))
        if source_features & ClimateEntityFeature.TURN_ON:
            await self.async_call_source("turn_on")
            return
        # Fall back to the first non-off mode the source offers.
        for mode in self.hvac_modes:
            if mode != HVACMode.OFF:
                await self.async_call_source("set_hvac_mode", hvac_mode=mode)
                return

    async def async_turn_off(self) -> None:
        source_features = ClimateEntityFeature(int(self.source_attr(ATTR_SUPPORTED_FEATURES, 0) or 0))
        if source_features & ClimateEntityFeature.TURN_OFF:
            await self.async_call_source("turn_off")
        else:
            await self.async_call_source("set_hvac_mode", hvac_mode=HVACMode.OFF)
