"""Fixtures: a fake Daikin Airbase climate entity and mocked climate services."""

from __future__ import annotations

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.core import HomeAssistant, ServiceCall

from custom_components.homekit_climate_proxy.const import (
    CONF_CLIMATE_ENTITY,
    CONF_CREATE_FAN,
    CONF_FAN_MAPPING,
    CONF_FAN_OFF_TURNS_OFF_CLIMATE,
    CONF_HIDE_HVAC_MODES,
    CONF_MODE_SWITCHES,
    CONF_SWITCH_OFF_MODE,
    DOMAIN,
)

SOURCE = "climate.daikin_airbase"
AIRBASE_FAN_MODES = ["Auto", "Low", "Mid", "High", "Low/Auto", "Mid/Auto", "High/Auto"]


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable loading of custom integrations."""


def set_source(hass: HomeAssistant, state: str = "cool", **extra) -> None:
    """Set the fake Daikin climate state."""
    attrs = {
        "hvac_modes": ["fan_only", "dry", "cool", "heat", "heat_cool", "off"],
        "min_temp": 7,
        "max_temp": 35,
        "target_temp_step": 1,
        "fan_modes": AIRBASE_FAN_MODES,
        "swing_modes": ["Off", "Vertical"],
        "current_temperature": 23.5,
        "temperature": 21.0,
        "fan_mode": "Mid",
        "swing_mode": "Off",
        "hvac_action": "cooling",
        "supported_features": 1 | 8 | 32 | 128 | 256,  # target temp, fan, swing, turn on, turn off
        "friendly_name": "Daikin",
    }
    attrs.update(extra)
    hass.states.async_set(SOURCE, state, attrs)


CLIMATE_SERVICES = ("set_fan_mode", "set_hvac_mode", "set_temperature", "set_swing_mode", "turn_on", "turn_off")


@pytest.fixture
def services() -> dict[str, list]:
    """Recorded calls per climate service; filled once the proxy is set up.

    The proxy's own climate platform loads the real climate services, which
    would replace mocks registered earlier, so the mocks are installed after
    the config entry has been set up (see ``setup_entry``).
    """
    return {}


def mock_climate_services(hass: HomeAssistant, calls: dict[str, list]) -> None:
    """Record climate service calls aimed at the fake source entity.

    Calls aimed at other entities (the proxy itself) still reach the real
    climate service handler, so the proxy's forwarding is exercised end to end.
    """
    for service in CLIMATE_SERVICES:
        recorded: list[ServiceCall] = []
        calls[service] = recorded
        original = hass.services.async_services_for_domain("climate")[service]

        async def handler(call: ServiceCall, _original=original, _recorded=recorded) -> None:
            target = call.data.get("entity_id")
            targets = target if isinstance(target, list) else [target]
            if SOURCE in targets:
                _recorded.append(call)
                return
            await hass.async_run_hass_job(_original.job, call)

        hass.services.async_register("climate", service, handler, schema=original.schema)


def make_entry(**options) -> MockConfigEntry:
    opts = {
        CONF_FAN_MAPPING: {},
        CONF_CREATE_FAN: True,
        CONF_FAN_OFF_TURNS_OFF_CLIMATE: True,
        CONF_HIDE_HVAC_MODES: [],
        CONF_MODE_SWITCHES: True,
        CONF_SWITCH_OFF_MODE: "previous",
    }
    opts.update(options)
    return MockConfigEntry(
        domain=DOMAIN,
        title="Air Conditioner",
        unique_id=SOURCE,
        data={CONF_CLIMATE_ENTITY: SOURCE, "name": "Air Conditioner"},
        options=opts,
    )


@pytest.fixture
async def setup_entry(hass: HomeAssistant, services):
    async def _setup(**options) -> MockConfigEntry:
        set_source(hass)
        entry = make_entry(**options)
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        mock_climate_services(hass, services)
        return entry

    return _setup


def data_of(call: ServiceCall) -> dict:
    """Service data with the schema normalisation undone (plain entity id, plain strings)."""
    data = {}
    for key, value in call.data.items():
        if key == "entity_id" and isinstance(value, list) and len(value) == 1:
            value = value[0]
        if hasattr(value, "value"):
            value = value.value
        data[key] = value
    return data
