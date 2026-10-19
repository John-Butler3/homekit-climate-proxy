"""Translate a climate entity's fan modes into HomeKit-friendly names.

The Home Assistant HomeKit Bridge exposes a thermostat's fan speed only for
fan modes called ``low``, ``medium``/``middle`` and ``high`` (plus ``auto``).
Many integrations use other names; the Daikin Airbase for example reports
``Auto, Low, Mid, High, Low/Auto, Mid/Auto, High/Auto``. This module builds
a two-way mapping so the proxy entity can present ``auto, low, medium, high``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re

from .const import (
    ORDERED_SPEEDS,
    TARGET_AUTO,
    TARGET_HIDE,
    TARGET_HIGH,
    TARGET_LOW,
    TARGET_MEDIUM,
    TARGET_OFF,
    TARGET_ON,
    TARGETS,
)

_LOW = re.compile(r"\b(low|lo|min|minimum|quiet|silent|silence|night|sleep|gentle|1)\b")
_MEDIUM = re.compile(r"\b(mid|middle|medium|med|normal|standard|balanced|2|3)\b")
_HIGH = re.compile(r"\b(high|hi|max|maximum|turbo|strong|powerful|boost|4|5)\b")


def normalize(value: str) -> str:
    """Lower-case and collapse separators so 'Low/Auto' -> 'low auto'."""
    return re.sub(r"[\s_/\-]+", " ", value.strip().lower())


def classify(source_mode: str) -> str:
    """Guess the HomeKit target for one source fan mode."""
    n = normalize(source_mode)
    if n in (TARGET_ON, TARGET_OFF):
        return n
    if "auto" in n:
        return TARGET_AUTO
    if _LOW.search(n):
        return TARGET_LOW
    if _MEDIUM.search(n):
        return TARGET_MEDIUM
    if _HIGH.search(n):
        return TARGET_HIGH
    return TARGET_HIDE


def default_mapping(source_modes: list[str]) -> dict[str, str]:
    """Build the default source -> target mapping for a list of fan modes.

    Numeric-only lists ("1".."5") are spread over low / medium / high.
    """
    modes = [m for m in source_modes if isinstance(m, str) and m.strip()]
    numeric = [m for m in modes if m.strip().isdigit()]
    mapping = {m: classify(m) for m in modes}
    if len(numeric) >= 2:
        ordered = sorted(numeric, key=lambda m: int(m))
        for i, m in enumerate(ordered):
            if i == 0:
                mapping[m] = TARGET_LOW
            elif i == len(ordered) - 1:
                mapping[m] = TARGET_HIGH
            elif len(ordered) == 3 or i == len(ordered) // 2:
                mapping[m] = TARGET_MEDIUM
            else:
                mapping[m] = TARGET_HIDE
    return mapping


def parse_mapping_text(text: str | None) -> dict[str, str]:
    """Parse ``Source: target`` lines (one per line, or comma separated)."""
    mapping: dict[str, str] = {}
    if not text:
        return mapping
    for chunk in re.split(r"[\n,;]+", text):
        chunk = chunk.strip()
        if not chunk:
            continue
        source, sep, target = chunk.rpartition(":")
        if not sep:
            source, sep, target = chunk.rpartition("=")
        source, target = source.strip(), target.strip().lower()
        if not source or target not in TARGETS:
            raise ValueError(chunk)
        mapping[source] = target
    return mapping


def mapping_to_text(mapping: dict[str, str]) -> str:
    """Render a mapping for the options form."""
    return "\n".join(f"{source}: {target}" for source, target in mapping.items())


@dataclass
class FanModeMap:
    """Two-way fan mode translation for one climate entity."""

    source_to_target: dict[str, str]
    #: Preferred source mode for each exposed target.
    target_to_source: dict[str, str] = field(init=False)
    #: Targets exposed as the proxy's fan_modes, in HomeKit order.
    targets: list[str] = field(init=False)

    def __post_init__(self) -> None:
        self.target_to_source = {}
        for source, target in self.source_to_target.items():
            if target == TARGET_HIDE:
                continue
            current = self.target_to_source.get(target)
            # Prefer the source literally named like the target ("Auto" for
            # auto rather than "Low/Auto"), otherwise the first one seen.
            if current is None or (normalize(source) == target and normalize(current) != target):
                self.target_to_source[target] = source
        order = [TARGET_AUTO, *ORDERED_SPEEDS, TARGET_ON, TARGET_OFF]
        self.targets = [t for t in order if t in self.target_to_source]

    @classmethod
    def from_modes(cls, source_modes: list[str], overrides: dict[str, str] | None = None) -> FanModeMap:
        """Default mapping for the modes, with user overrides applied."""
        mapping = default_mapping(source_modes)
        for source, target in (overrides or {}).items():
            if source in mapping or source in source_modes:
                mapping[source] = target
        return cls(mapping)

    @property
    def speeds(self) -> list[str]:
        """Exposed speed steps (low/medium/high) in order."""
        return [t for t in ORDERED_SPEEDS if t in self.target_to_source]

    def to_target(self, source_mode: str | None) -> str | None:
        """Translate the entity's current fan mode."""
        if source_mode is None:
            return None
        target = self.source_to_target.get(source_mode)
        if target is None:
            # Case-insensitive fallback (integrations sometimes change case).
            for source, candidate in self.source_to_target.items():
                if normalize(source) == normalize(source_mode):
                    target = candidate
                    break
        if target is None or target == TARGET_HIDE:
            return None
        return target

    def to_source(self, target: str) -> str | None:
        """Translate a HomeKit-friendly mode back to the entity's mode."""
        return self.target_to_source.get(target.lower())
