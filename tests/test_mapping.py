"""Tests for the fan mode mapping."""

import pytest

from custom_components.homekit_climate_proxy.mapping import (
    FanModeMap,
    classify,
    default_mapping,
    mapping_to_text,
    parse_mapping_text,
)


def test_airbase_default_mapping() -> None:
    modes = ["Auto", "Low", "Mid", "High", "Low/Auto", "Mid/Auto", "High/Auto"]
    assert default_mapping(modes) == {
        "Auto": "auto",
        "Low": "low",
        "Mid": "medium",
        "High": "high",
        "Low/Auto": "auto",
        "Mid/Auto": "auto",
        "High/Auto": "auto",
    }
    fan_map = FanModeMap.from_modes(modes)
    assert fan_map.targets == ["auto", "low", "medium", "high"]
    assert fan_map.speeds == ["low", "medium", "high"]
    assert fan_map.to_source("auto") == "Auto"  # not "Low/Auto"
    assert fan_map.to_source("medium") == "Mid"
    assert fan_map.to_target("Mid/Auto") == "auto"
    assert fan_map.to_target("mid") == "medium"
    assert fan_map.to_target("Bogus") is None


def test_airbase_without_auto() -> None:
    fan_map = FanModeMap.from_modes(["Low", "Mid", "High"])
    assert fan_map.targets == ["low", "medium", "high"]
    assert fan_map.to_source("auto") is None


def test_numeric_and_named_levels() -> None:
    assert default_mapping(["1", "2", "3", "4", "5", "Auto", "Silence"]) == {
        "1": "low",
        "2": "hide",
        "3": "medium",
        "4": "hide",
        "5": "high",
        "Auto": "auto",
        "Silence": "low",
    }
    assert classify("Quiet") == "low"
    assert classify("Turbo") == "high"
    assert classify("Weird") == "hide"


def test_overrides_and_text_round_trip() -> None:
    fan_map = FanModeMap.from_modes(["Auto", "Low", "Mid", "High"], {"Mid": "high", "High": "hide"})
    assert fan_map.targets == ["auto", "low", "high"]
    assert fan_map.to_source("high") == "Mid"
    text = mapping_to_text({"Low": "low", "Mid": "medium"})
    assert parse_mapping_text(text) == {"Low": "low", "Mid": "medium"}
    assert parse_mapping_text("Low/Auto: auto, High = high") == {"Low/Auto": "auto", "High": "high"}
    with pytest.raises(ValueError):
        parse_mapping_text("Low: fast")
