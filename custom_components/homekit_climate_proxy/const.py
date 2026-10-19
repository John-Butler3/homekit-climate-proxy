"""Constants for HomeKit Climate Proxy."""

from __future__ import annotations

from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "homekit_climate_proxy"
PLATFORMS: Final = [Platform.CLIMATE, Platform.FAN, Platform.SWITCH]

CONF_CLIMATE_ENTITY: Final = "climate_entity"
CONF_FAN_MAPPING: Final = "fan_mapping"
CONF_CREATE_FAN: Final = "create_fan"
CONF_FAN_OFF_TURNS_OFF_CLIMATE: Final = "fan_off_turns_off_climate"
CONF_HIDE_HVAC_MODES: Final = "hide_hvac_modes"
CONF_MODE_SWITCHES: Final = "mode_switches"
CONF_SWITCH_OFF_MODE: Final = "switch_off_mode"

SWITCH_OFF_PREVIOUS: Final = "previous"
SWITCH_OFF_OFF: Final = "off"
SWITCH_OFF_COOL: Final = "cool"
SWITCH_OFF_MODES: Final = [SWITCH_OFF_PREVIOUS, SWITCH_OFF_OFF, SWITCH_OFF_COOL]

# HVAC modes HomeKit's thermostat cannot express; offered as switches instead.
SWITCHABLE_MODES: Final = ["fan_only", "dry"]
# HVAC modes HomeKit's thermostat can express (used to remember the "previous" mode).
REGULAR_MODES: Final = ["heat", "cool", "heat_cool", "auto"]

DEFAULT_NAME: Final = "Air Conditioner"

# HomeKit-friendly fan mode names (what the HomeKit Bridge understands).
TARGET_AUTO: Final = "auto"
TARGET_LOW: Final = "low"
TARGET_MEDIUM: Final = "medium"
TARGET_HIGH: Final = "high"
TARGET_ON: Final = "on"
TARGET_OFF: Final = "off"
TARGET_HIDE: Final = "hide"
TARGETS: Final = [TARGET_AUTO, TARGET_LOW, TARGET_MEDIUM, TARGET_HIGH, TARGET_ON, TARGET_OFF, TARGET_HIDE]
ORDERED_SPEEDS: Final = [TARGET_LOW, TARGET_MEDIUM, TARGET_HIGH]
