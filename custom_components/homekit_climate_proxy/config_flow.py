"""Config flow for HomeKit Climate Proxy."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.climate import ATTR_FAN_MODES, ATTR_HVAC_MODES
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    BooleanSelector,
    EntitySelector,
    EntitySelectorConfig,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

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
    SWITCH_OFF_MODES,
    SWITCH_OFF_PREVIOUS,
)
from .mapping import default_mapping, mapping_to_text, parse_mapping_text


def _options_schema(hvac_modes: list[str]) -> vol.Schema:
    hideable = [m for m in hvac_modes if m != "off"] or ["heat_cool", "auto", "fan_only", "dry"]
    return vol.Schema(
        {
            vol.Optional(CONF_FAN_MAPPING): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT, multiline=True)),
            vol.Optional(CONF_HIDE_HVAC_MODES, default=[]): SelectSelector(
                SelectSelectorConfig(options=hideable, multiple=True, mode=SelectSelectorMode.LIST, translation_key="hvac_mode")
            ),
            vol.Required(CONF_MODE_SWITCHES, default=True): BooleanSelector(),
            vol.Required(CONF_SWITCH_OFF_MODE, default=SWITCH_OFF_PREVIOUS): SelectSelector(
                SelectSelectorConfig(options=SWITCH_OFF_MODES, mode=SelectSelectorMode.DROPDOWN, translation_key=CONF_SWITCH_OFF_MODE)
            ),
            vol.Required(CONF_CREATE_FAN, default=True): BooleanSelector(),
            vol.Required(CONF_FAN_OFF_TURNS_OFF_CLIMATE, default=True): BooleanSelector(),
        }
    )


def _collect_options(user_input: dict[str, Any]) -> dict[str, Any]:
    return {
        CONF_FAN_MAPPING: parse_mapping_text(user_input.get(CONF_FAN_MAPPING)),
        CONF_HIDE_HVAC_MODES: list(user_input.get(CONF_HIDE_HVAC_MODES) or []),
        CONF_MODE_SWITCHES: user_input[CONF_MODE_SWITCHES],
        CONF_SWITCH_OFF_MODE: user_input[CONF_SWITCH_OFF_MODE],
        CONF_CREATE_FAN: user_input[CONF_CREATE_FAN],
        CONF_FAN_OFF_TURNS_OFF_CLIMATE: user_input[CONF_FAN_OFF_TURNS_OFF_CLIMATE],
    }


class HomekitClimateProxyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Pick the climate entity, then confirm the fan mode mapping."""

    VERSION = 1

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self._source_modes: list[str] = []
        self._hvac_modes: list[str] = []

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> HomekitClimateProxyOptionsFlow:
        return HomekitClimateProxyOptionsFlow()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            entity_id = user_input[CONF_CLIMATE_ENTITY]
            await self.async_set_unique_id(entity_id)
            self._abort_if_unique_id_configured()
            state = self.hass.states.get(entity_id)
            if state is None:
                errors[CONF_CLIMATE_ENTITY] = "entity_not_found"
            else:
                self._data = {CONF_CLIMATE_ENTITY: entity_id, CONF_NAME: user_input[CONF_NAME].strip() or DEFAULT_NAME}
                self._source_modes = list(state.attributes.get(ATTR_FAN_MODES) or [])
                self._hvac_modes = [str(m) for m in state.attributes.get(ATTR_HVAC_MODES) or []]
                return await self.async_step_mapping()
        schema = vol.Schema(
            {
                vol.Required(CONF_CLIMATE_ENTITY): EntitySelector(EntitySelectorConfig(domain="climate")),
                vol.Required(CONF_NAME, default=DEFAULT_NAME): TextSelector(),
            }
        )
        return self.async_show_form(
            step_id="user", data_schema=self.add_suggested_values_to_schema(schema, user_input), errors=errors
        )

    async def async_step_mapping(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                options = _collect_options(user_input)
            except ValueError:
                errors[CONF_FAN_MAPPING] = "invalid_mapping"
            else:
                return self.async_create_entry(title=self._data[CONF_NAME], data=self._data, options=options)
        suggested = {
            CONF_FAN_MAPPING: mapping_to_text(default_mapping(self._source_modes)),
            # HomeKit's "Auto" maps to heat_cool, which many units handle poorly.
            CONF_HIDE_HVAC_MODES: [m for m in ("heat_cool",) if m in self._hvac_modes],
        }
        return self.async_show_form(
            step_id="mapping",
            data_schema=self.add_suggested_values_to_schema(_options_schema(self._hvac_modes), user_input or suggested),
            errors=errors,
            description_placeholders={"modes": ", ".join(self._source_modes) or "none"},
        )


class HomekitClimateProxyOptionsFlow(OptionsFlow):
    """Edit the mapping and the fan entity options later."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        entity_id = self.config_entry.data[CONF_CLIMATE_ENTITY]
        state = self.hass.states.get(entity_id)
        source_modes = list(state.attributes.get(ATTR_FAN_MODES) or []) if state else []
        hvac_modes = [str(m) for m in (state.attributes.get(ATTR_HVAC_MODES) if state else None) or []]
        if user_input is not None:
            try:
                options = _collect_options(user_input)
            except ValueError:
                errors[CONF_FAN_MAPPING] = "invalid_mapping"
            else:
                return self.async_create_entry(title="", data=options)
        current = dict(self.config_entry.options)
        mapping = default_mapping(source_modes)
        mapping.update({k: v for k, v in (current.get(CONF_FAN_MAPPING) or {}).items()})
        suggested = {
            CONF_FAN_MAPPING: mapping_to_text(mapping),
            CONF_HIDE_HVAC_MODES: list(current.get(CONF_HIDE_HVAC_MODES) or []),
            CONF_MODE_SWITCHES: current.get(CONF_MODE_SWITCHES, True),
            CONF_SWITCH_OFF_MODE: current.get(CONF_SWITCH_OFF_MODE, SWITCH_OFF_PREVIOUS),
            CONF_CREATE_FAN: current.get(CONF_CREATE_FAN, True),
            CONF_FAN_OFF_TURNS_OFF_CLIMATE: current.get(CONF_FAN_OFF_TURNS_OFF_CLIMATE, True),
        }
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(_options_schema(hvac_modes), user_input or suggested),
            errors=errors,
            description_placeholders={"modes": ", ".join(source_modes) or "none"},
        )
