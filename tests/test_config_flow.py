"""Config flow tests."""

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.homekit_climate_proxy.const import (
    CONF_CLIMATE_ENTITY,
    CONF_CREATE_FAN,
    CONF_FAN_MAPPING,
    CONF_FAN_OFF_TURNS_OFF_CLIMATE,
    CONF_HIDE_HVAC_MODES,
    CONF_MODE_SWITCHES,
    CONF_SWITCH_OFF_MODE,
    CONF_AUTO_MODE,
    DOMAIN,
)

from .conftest import SOURCE, set_source

FULL_INPUT = {
    CONF_CREATE_FAN: False,
    CONF_FAN_OFF_TURNS_OFF_CLIMATE: False,
    CONF_MODE_SWITCHES: True,
    CONF_SWITCH_OFF_MODE: "previous",
    CONF_HIDE_HVAC_MODES: [],
    CONF_AUTO_MODE: "fan_only",
}


def _suggested(result, key):
    return next(k.description["suggested_value"] for k in result["data_schema"].schema if k.schema == key)


async def test_full_flow(hass: HomeAssistant) -> None:
    set_source(hass)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["step_id"] == "user"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_CLIMATE_ENTITY: SOURCE, "name": "Living room AC"}
    )
    assert result["step_id"] == "mapping"
    assert "Mid" in result["description_placeholders"]["modes"]
    mapping_text = _suggested(result, CONF_FAN_MAPPING)
    assert "Mid: medium" in mapping_text
    assert _suggested(result, CONF_AUTO_MODE) == "fan_only"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_FAN_MAPPING: mapping_text, **FULL_INPUT}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"][CONF_FAN_MAPPING]["Mid"] == "medium"
    assert result["options"][CONF_AUTO_MODE] == "fan_only"
    assert result["options"][CONF_FAN_OFF_TURNS_OFF_CLIMATE] is False
    await hass.async_block_till_done()
    assert hass.states.get("climate.living_room_ac") is not None
    assert "heat_cool" in hass.states.get("climate.living_room_ac").attributes["hvac_modes"]


async def test_invalid_mapping(hass: HomeAssistant) -> None:
    set_source(hass)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_CLIMATE_ENTITY: SOURCE, "name": "AC"})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_FAN_MAPPING: "Mid: fastest", **FULL_INPUT}
    )
    assert result["errors"] == {CONF_FAN_MAPPING: "invalid_mapping"}


async def test_options_flow(hass: HomeAssistant, setup_entry) -> None:
    entry = await setup_entry()
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["step_id"] == "init"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_FAN_MAPPING: "Auto: auto\nLow: low\nMid: medium\nHigh: high", **FULL_INPUT, CONF_MODE_SWITCHES: False},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.options[CONF_MODE_SWITCHES] is False
    assert hass.states.get("switch.air_conditioner_dry_mode") is None
