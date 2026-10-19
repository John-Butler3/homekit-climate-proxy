"""Base entity: mirrors a source climate entity's state."""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate import ATTR_FAN_MODE, ATTR_FAN_MODES
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Event, EventStateChangedData, State, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_state_change_event

from . import ProxyData
from .mapping import FanModeMap


class ProxyEntity(Entity):
    """Entity that follows the source climate entity."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, data: ProxyData, key: str) -> None:
        self._data = data
        self._attr_unique_id = f"{data.entry.entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={data.device_identifier},
            name=data.name,
            manufacturer="HomeKit Climate Proxy",
            model="Climate proxy",
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            async_track_state_change_event(self.hass, [self._data.climate_entity_id], self._async_source_changed)
        )

    @callback
    def _async_source_changed(self, event: Event[EventStateChangedData]) -> None:
        self.async_write_ha_state()

    # ---------------------------------------------------------------- source

    @property
    def source(self) -> State | None:
        return self.hass.states.get(self._data.climate_entity_id)

    @property
    def available(self) -> bool:
        source = self.source
        return source is not None and source.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN)

    def source_attr(self, key: str, default: Any = None) -> Any:
        source = self.source
        if source is None:
            return default
        return source.attributes.get(key, default)

    @property
    def fan_map(self) -> FanModeMap:
        return self._data.fan_map(self.source_attr(ATTR_FAN_MODES))

    @property
    def source_fan_mode(self) -> str | None:
        return self.source_attr(ATTR_FAN_MODE)

    async def async_call_source(self, service: str, **data: Any) -> None:
        await self.hass.services.async_call(
            "climate",
            service,
            {ATTR_ENTITY_ID: self._data.climate_entity_id, **data},
            blocking=True,
            context=self._context,
        )
