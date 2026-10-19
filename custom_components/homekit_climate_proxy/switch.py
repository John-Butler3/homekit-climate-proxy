"""Switches for HVAC modes HomeKit's thermostat cannot express (fan only, dry)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate import ATTR_HVAC_MODES, HVACMode
from homeassistant.components.switch import SwitchEntity
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ProxyConfigEntry, ProxyData
from .const import REGULAR_MODES, SWITCH_OFF_COOL, SWITCH_OFF_OFF, SWITCHABLE_MODES
from .entity import ProxyEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ProxyConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    data = entry.runtime_data
    if not data.mode_switches:
        return
    source = hass.states.get(data.climate_entity_id)
    available = list((source.attributes.get(ATTR_HVAC_MODES) if source else None) or SWITCHABLE_MODES)
    async_add_entities(ModeSwitch(data, mode) for mode in SWITCHABLE_MODES if mode in available)


class ModeSwitch(ProxyEntity, SwitchEntity):
    """On = the air conditioner runs in this mode (fan only / dry)."""

    def __init__(self, data: ProxyData, mode: str) -> None:
        super().__init__(data, mode)
        self._mode = mode

    @property
    def is_on(self) -> bool:
        source = self.source
        return source is not None and source.state == self._mode

    @callback
    def _async_source_changed(self, event: Event[EventStateChangedData]) -> None:
        new_state = event.data.get("new_state")
        if new_state is not None and new_state.state in REGULAR_MODES:
            self._data.last_regular_mode = new_state.state
        super()._async_source_changed(event)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        source = self.source
        if source is not None and source.state in REGULAR_MODES:
            self._data.last_regular_mode = source.state

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"hvac_mode": self._mode, "previous_mode": self._data.last_regular_mode}

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.async_call_source("set_hvac_mode", hvac_mode=self._mode)

    async def async_turn_off(self, **kwargs: Any) -> None:
        if not self.is_on:
            return
        choice = self._data.switch_off_mode
        if choice == SWITCH_OFF_OFF:
            target = HVACMode.OFF
        elif choice == SWITCH_OFF_COOL:
            target = HVACMode.COOL
        else:
            target = self._data.last_regular_mode or HVACMode.OFF
        await self.async_call_source("set_hvac_mode", hvac_mode=target)
