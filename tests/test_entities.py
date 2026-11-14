"""Tests for the proxy climate, fan and switch entities."""

from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from .conftest import SOURCE, data_of, set_source

PROXY = "climate.air_conditioner"
FAN = "fan.air_conditioner_fan"
FAN_ONLY = "switch.air_conditioner_fan_only_mode"
DRY = "switch.air_conditioner_dry_mode"


async def test_proxy_mirrors_source(hass: HomeAssistant, setup_entry) -> None:
    await setup_entry()
    state = hass.states.get(PROXY)
    assert state is not None
    assert state.state == "cool"
    assert state.attributes["fan_modes"] == ["auto", "low", "medium", "high"]
    assert state.attributes["fan_mode"] == "medium"
    assert state.attributes["current_temperature"] == 23.5
    assert state.attributes["temperature"] == 21.0
    assert state.attributes["hvac_action"] == "cooling"
    assert state.attributes["swing_modes"] == ["Off", "Vertical"]
    assert state.attributes["min_temp"] == 7
    assert state.attributes["hvac_modes"] == ["fan_only", "dry", "cool", "heat", "heat_cool", "off"]
    assert state.attributes["supported_features"] & 8  # FAN_MODE

    set_source(hass, "heat", fan_mode="Low/Auto")
    await hass.async_block_till_done()
    state = hass.states.get(PROXY)
    assert state.state == "heat"
    assert state.attributes["fan_mode"] == "auto"

    hass.states.async_set(SOURCE, STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    assert hass.states.get(PROXY).state == STATE_UNAVAILABLE


async def test_fan_mode_is_translated(hass: HomeAssistant, setup_entry, services) -> None:
    await setup_entry()
    await hass.services.async_call("climate", "set_fan_mode", {"entity_id": PROXY, "fan_mode": "medium"}, blocking=True)
    assert data_of(services["set_fan_mode"][-1]) == {"entity_id": SOURCE, "fan_mode": "Mid"}
    await hass.services.async_call("climate", "set_fan_mode", {"entity_id": PROXY, "fan_mode": "auto"}, blocking=True)
    assert data_of(services["set_fan_mode"][-1]) == {"entity_id": SOURCE, "fan_mode": "Auto"}


async def test_other_commands_are_forwarded(hass: HomeAssistant, setup_entry, services) -> None:
    await setup_entry()
    await hass.services.async_call("climate", "set_temperature", {"entity_id": PROXY, "temperature": 24}, blocking=True)
    assert data_of(services["set_temperature"][-1]) == {"entity_id": SOURCE, "temperature": 24}
    await hass.services.async_call("climate", "set_hvac_mode", {"entity_id": PROXY, "hvac_mode": "heat"}, blocking=True)
    assert data_of(services["set_hvac_mode"][-1]) == {"entity_id": SOURCE, "hvac_mode": "heat"}
    await hass.services.async_call(
        "climate", "set_swing_mode", {"entity_id": PROXY, "swing_mode": "Vertical"}, blocking=True
    )
    assert data_of(services["set_swing_mode"][-1]) == {"entity_id": SOURCE, "swing_mode": "Vertical"}
    await hass.services.async_call("climate", "turn_off", {"entity_id": PROXY}, blocking=True)
    assert len(services["turn_off"]) == 1
    await hass.services.async_call("climate", "turn_on", {"entity_id": PROXY}, blocking=True)
    assert len(services["turn_on"]) == 1


async def test_no_fan_entity_by_default(hass: HomeAssistant, setup_entry) -> None:
    await setup_entry()
    assert hass.states.get(FAN) is None


async def test_fan_entity(hass: HomeAssistant, setup_entry, services) -> None:
    await setup_entry(create_fan=True)
    fan = hass.states.get(FAN)
    assert fan is not None
    assert fan.state == STATE_ON
    assert fan.attributes["percentage"] == 66  # medium of low/medium/high
    assert fan.attributes["preset_modes"] == ["auto"]

    await hass.services.async_call("fan", "set_percentage", {"entity_id": FAN, "percentage": 100}, blocking=True)
    assert data_of(services["set_fan_mode"][-1]) == {"entity_id": SOURCE, "fan_mode": "High"}
    await hass.services.async_call("fan", "set_preset_mode", {"entity_id": FAN, "preset_mode": "auto"}, blocking=True)
    assert data_of(services["set_fan_mode"][-1]) == {"entity_id": SOURCE, "fan_mode": "Auto"}

    set_source(hass, "heat", fan_mode="Low/Auto")
    await hass.async_block_till_done()
    fan = hass.states.get(FAN)
    assert fan.attributes["preset_mode"] == "auto"
    assert fan.attributes["percentage"] is None

    # Fan off turns the air conditioner off; turning on while off switches the climate on first.
    await hass.services.async_call("fan", "turn_off", {"entity_id": FAN}, blocking=True)
    assert data_of(services["set_hvac_mode"][-1]) == {"entity_id": SOURCE, "hvac_mode": "off"}
    set_source(hass, "off")
    await hass.async_block_till_done()
    assert hass.states.get(FAN).state == STATE_OFF
    await hass.services.async_call("fan", "turn_on", {"entity_id": FAN, "percentage": 33}, blocking=True)
    assert len(services["turn_on"]) == 1
    assert data_of(services["set_fan_mode"][-1]) == {"entity_id": SOURCE, "fan_mode": "Low"}


async def test_mode_switches(hass: HomeAssistant, setup_entry, services) -> None:
    await setup_entry()
    assert hass.states.get(FAN_ONLY).state == STATE_OFF
    assert hass.states.get(DRY).state == STATE_OFF

    await hass.services.async_call("switch", "turn_on", {"entity_id": DRY}, blocking=True)
    assert data_of(services["set_hvac_mode"][-1]) == {"entity_id": SOURCE, "hvac_mode": "dry"}
    set_source(hass, "dry")
    await hass.async_block_till_done()
    assert hass.states.get(DRY).state == STATE_ON
    assert hass.states.get(FAN_ONLY).state == STATE_OFF

    # Off returns to the previous regular mode (cool).
    await hass.services.async_call("switch", "turn_off", {"entity_id": DRY}, blocking=True)
    assert data_of(services["set_hvac_mode"][-1]) == {"entity_id": SOURCE, "hvac_mode": "cool"}

    await hass.services.async_call("switch", "turn_on", {"entity_id": FAN_ONLY}, blocking=True)
    assert data_of(services["set_hvac_mode"][-1]) == {"entity_id": SOURCE, "hvac_mode": "fan_only"}


async def test_switch_off_mode_option(hass: HomeAssistant, setup_entry, services) -> None:
    await setup_entry(switch_off_mode="off")
    set_source(hass, "fan_only")
    await hass.async_block_till_done()
    await hass.services.async_call("switch", "turn_off", {"entity_id": FAN_ONLY}, blocking=True)
    assert data_of(services["set_hvac_mode"][-1]) == {"entity_id": SOURCE, "hvac_mode": "off"}


async def test_homekit_auto_is_fan_only(hass: HomeAssistant, setup_entry, services) -> None:
    await setup_entry(homekit_auto_mode="fan_only")
    state = hass.states.get(PROXY)
    assert "heat_cool" in state.attributes["hvac_modes"]
    # HomeKit Auto -> Daikin fan only
    await hass.services.async_call("climate", "set_hvac_mode", {"entity_id": PROXY, "hvac_mode": "heat_cool"}, blocking=True)
    assert data_of(services["set_hvac_mode"][-1]) == {"entity_id": SOURCE, "hvac_mode": "fan_only"}
    # Daikin in fan only -> shown as heat_cool (Auto in the Home app)
    set_source(hass, "fan_only")
    await hass.async_block_till_done()
    assert hass.states.get(PROXY).state == "heat_cool"
    # Real heat_cool on the Daikin is not selectable anymore and shows as cool
    set_source(hass, "heat_cool")
    await hass.async_block_till_done()
    assert hass.states.get(PROXY).state == "cool"
    # set_temperature with heat_cool is translated too
    await hass.services.async_call(
        "climate", "set_temperature", {"entity_id": PROXY, "temperature": 22, "hvac_mode": "heat_cool"}, blocking=True
    )
    assert data_of(services["set_temperature"][-1]) == {"entity_id": SOURCE, "temperature": 22, "hvac_mode": "fan_only"}


async def test_fan_off_mode(hass: HomeAssistant, setup_entry, services) -> None:
    await setup_entry(fan_off_mode=True)
    state = hass.states.get(PROXY)
    assert state.attributes["fan_modes"] == ["auto", "low", "medium", "high", "off"]
    assert state.attributes["fan_mode"] == "medium"
    # 0 % on the slider -> "off" -> unit off
    await hass.services.async_call("climate", "set_fan_mode", {"entity_id": PROXY, "fan_mode": "off"}, blocking=True)
    assert len(services["turn_off"]) == 1
    set_source(hass, "off")
    await hass.async_block_till_done()
    assert hass.states.get(PROXY).attributes["fan_mode"] == "off"
    # A speed while off switches the unit on, then sets the speed
    await hass.services.async_call("climate", "set_fan_mode", {"entity_id": PROXY, "fan_mode": "high"}, blocking=True)
    assert len(services["turn_on"]) == 1
    assert data_of(services["set_fan_mode"][-1]) == {"entity_id": SOURCE, "fan_mode": "High"}


async def test_homekit_auto_hidden(hass: HomeAssistant, setup_entry) -> None:
    await setup_entry(homekit_auto_mode="hidden")
    assert "heat_cool" not in hass.states.get(PROXY).attributes["hvac_modes"]


async def test_hidden_modes_and_disabled_extras(hass: HomeAssistant, setup_entry) -> None:
    await setup_entry(fan_mapping={"Mid": "hide"}, mode_switches=False, hide_hvac_modes=["heat_cool"])
    assert hass.states.get(FAN) is None
    assert hass.states.get(DRY) is None
    state = hass.states.get(PROXY)
    assert state.attributes["fan_modes"] == ["auto", "low", "high"]
    assert state.attributes["fan_mode"] is None  # source is on Mid, which is hidden
    assert "heat_cool" not in state.attributes["hvac_modes"]
    # A hidden current mode is reported as the closest visible one.
    set_source(hass, "heat_cool")
    await hass.async_block_till_done()
    assert hass.states.get(PROXY).state == "cool"
