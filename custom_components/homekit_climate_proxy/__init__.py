"""HomeKit Climate Proxy.

Creates a HomeKit-friendly copy of a climate entity whose fan modes the
HomeKit Bridge cannot handle (for example the Daikin Airbase's "Mid" and
"Low/Auto"), plus an optional fan entity for direct speed control.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import (
    CONF_CLIMATE_ENTITY,
    CONF_CREATE_FAN,
    CONF_FAN_MAPPING,
    CONF_FAN_OFF_TURNS_OFF_CLIMATE,
    CONF_HIDE_HVAC_MODES,
    CONF_MODE_SWITCHES,
    CONF_SWITCH_OFF_MODE,
    DEFAULT_NAME,
    DOMAIN,
    PLATFORMS,
)
from .mapping import FanModeMap

_LOGGER = logging.getLogger(__name__)


@dataclass
class ProxyData:
    """Runtime data shared by the proxy entities."""

    entry: ConfigEntry
    name: str
    climate_entity_id: str
    overrides: dict[str, str]
    create_fan: bool
    fan_off_turns_off_climate: bool
    #: HVAC modes not shown to HomeKit (e.g. heat_cool when "Auto" misbehaves).
    hide_hvac_modes: set[str]
    #: Create "Fan only" / "Dry" switches for modes HomeKit cannot express.
    mode_switches: bool
    #: What turning such a switch off does: previous | off | cool.
    switch_off_mode: str
    #: Last heat/cool/auto mode seen on the source (runtime, for "previous").
    last_regular_mode: str | None = None

    @property
    def device_identifier(self) -> tuple[str, str]:
        return (DOMAIN, self.entry.entry_id)

    def fan_map(self, source_modes: list[str] | None) -> FanModeMap:
        """Mapping for the fan modes the source currently reports."""
        return FanModeMap.from_modes(list(source_modes or []), self.overrides)


type ProxyConfigEntry = ConfigEntry[ProxyData]


def build_data(entry: ConfigEntry) -> ProxyData:
    cfg = {**entry.data, **entry.options}
    return ProxyData(
        entry=entry,
        name=cfg.get("name") or entry.title or DEFAULT_NAME,
        climate_entity_id=cfg[CONF_CLIMATE_ENTITY],
        overrides=dict(cfg.get(CONF_FAN_MAPPING) or {}),
        create_fan=bool(cfg.get(CONF_CREATE_FAN, True)),
        fan_off_turns_off_climate=bool(cfg.get(CONF_FAN_OFF_TURNS_OFF_CLIMATE, True)),
        hide_hvac_modes=set(cfg.get(CONF_HIDE_HVAC_MODES) or []),
        mode_switches=bool(cfg.get(CONF_MODE_SWITCHES, True)),
        switch_off_mode=cfg.get(CONF_SWITCH_OFF_MODE) or "previous",
    )


async def async_setup_entry(hass: HomeAssistant, entry: ProxyConfigEntry) -> bool:
    data = build_data(entry)
    entry.runtime_data = data
    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={data.device_identifier},
        manufacturer="HomeKit Climate Proxy",
        model="Climate proxy",
        name=data.name,
    )
    registry = er.async_get(hass)
    for reg_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
        if (reg_entry.domain == "fan" and not data.create_fan) or (
            reg_entry.domain == "switch" and not data.mode_switches
        ):
            registry.async_remove(reg_entry.entity_id)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ProxyConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
