# HomeKit Climate Proxy

A small Home Assistant integration (HACS compatible) that makes an air
conditioner's **fan speed, fan-only and dry modes work in Apple Home** when the
built-in HomeKit Bridge cannot handle them. Written for the **Daikin Airbase**
(BRP15B61) but it works with any `climate` entity.

## The problems it solves

| Symptom in the Home app | Cause | What the proxy does |
| --- | --- | --- |
| Fan speed slider does nothing or shows the wrong speed | The HomeKit Bridge only recognises fan modes named `low`, `medium`/`middle`, `high` and `auto`. Daikin reports `Auto, Low, Mid, High, Low/Auto, Mid/Auto, High/Auto`, so `Mid` and the `/Auto` variants are invisible. | Exposes a copy of the climate entity whose fan modes are `auto, low, medium, high`, translating to and from the Daikin names. |
| No way to pick Fan only or Dry | HomeKit thermostats only have Off / Heat / Cool / Auto. | Adds a **Fan only mode** switch and a **Dry mode** switch. Turning one off returns to the previous heat/cool mode (configurable). |
| "Auto" in the Home app behaves badly | HomeKit Auto maps to Home Assistant `heat_cool`, which many Daikin units handle poorly. | Re-purposes HomeKit's **Auto** as **Fan only** (default) or Dry, or hides it. The Daikin's real heat/cool auto is then no longer reachable from HomeKit and shows as Cool while active. |

Everything else (temperature, mode, swing, presets, on/off) is forwarded to the
original entity unchanged, and the proxy follows its state in real time.

## Install

**HACS**: HACS → Integrations → ⋮ → Custom repositories → add this repository
(category *Integration*) → install → restart Home Assistant.

**Manual**: copy `custom_components/homekit_climate_proxy` into your
`config/custom_components/` folder and restart.

## Set up

1. Settings → Devices & services → Add integration → **HomeKit Climate Proxy**.
2. Pick the Daikin `climate` entity and a name (for example "Living room AC").
3. The next page shows the detected fan modes and a suggested mapping, e.g.

   ```
   Auto: auto
   Low: low
   Mid: medium
   High: high
   Low/Auto: auto
   Mid/Auto: auto
   High/Auto: auto
   ```

   Targets are `auto`, `low`, `medium`, `high`, `on`, `off` or `hide`.
   "What HomeKit's Auto mode does" defaults to **Fan only**: tapping Auto in the
   Home app puts the Daikin into fan-only mode, and fan-only shows as Auto.
   Choose Dry, the real heat/cool auto, or hide Auto instead. Keep the Fan only
   / Dry switches on if you also want them as separate tiles. A separate Fan
   accessory is available as an option but off by default, the thermostat
   already carries the fan speed.
4. In the HomeKit Bridge settings, **include the proxy entities and exclude the
   original Daikin climate entity**, otherwise Apple Home shows two thermostats:

   ```yaml
   homekit:
     - filter:
         include_entities:
           - climate.living_room_ac
           - switch.living_room_ac_fan_only_mode
           - switch.living_room_ac_dry_mode
         exclude_entities:
           - climate.daikin_airbase
   ```

   If the proxy replaces an entity that was already paired, remove the old
   thermostat from the Home app once; HomeKit caches the fan configuration it
   learned at pairing time.

All settings can be changed later via **Configure** on the integration entry.

## Notes

- Fan speed from the Home app: open the thermostat, the fan control is in its
  detail view. Home Assistant sets the slider step to 100 / number of speeds,
  so with Low / Mid / High the slider latches at 0 / 33 / 67 / 100 %. With the
  default "off" fan mode, 0 % switches the unit off and picking a speed while
  it is off switches it back on. Units with an Auto fan also get an Auto
  toggle. If your unit reports only two fan steps
  (`fan_modes` without `Mid`), the slider has 0 / 50 / 100 %; the proxy can
  only offer speeds the Daikin integration offers. Map `Auto: hide` if you
  want no Auto fan toggle.
- Dry and Fan only: Apple's thermostat has only Off / Heat / Cool / Auto, so
  these are switches. Turning "Dry mode" on puts the unit into dry; turning it
  off returns to the previous heat/cool mode (or off / cool, configurable).
  Both switches must be included in the HomeKit Bridge filter to appear in the
  Home app. Tip: add them to the same room as the thermostat and rename them
  "Dry" and "Fan only" in the Home app for Siri.
- Home Assistant itself is improving the HomeKit Bridge's fan-mode detection in
  newer releases; the proxy keeps working either way and still provides the
  Fan only / Dry switches and the Auto hiding.

## Development

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements_test.txt
pytest
```
