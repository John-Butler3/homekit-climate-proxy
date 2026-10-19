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
| "Auto" in the Home app behaves badly | HomeKit Auto maps to Home Assistant `heat_cool`, which many Daikin units handle poorly. | Lets you hide `heat_cool` (or any mode) from HomeKit. |
| Fan speed buried in thermostat settings | HomeKit shows the thermostat fan under the accessory settings only. | Optionally adds a separate **Fan** accessory with a speed slider and an Auto preset. |

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

   Targets are `auto`, `low`, `medium`, `high`, `on`, `off` or `hide`. `heat_cool`
   is pre-selected for hiding; untick it if Auto works for you. Keep the
   Fan only / Dry switches and the separate Fan entity unless you don't want them.
4. In the HomeKit Bridge settings, **include the proxy entities and exclude the
   original Daikin climate entity**, otherwise Apple Home shows two thermostats:

   ```yaml
   homekit:
     - filter:
         include_entities:
           - climate.living_room_ac
           - fan.living_room_ac_fan
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

- Fan speed from the Home app: the thermostat's fan slider maps 33 % / 66 % /
  100 % to Low / Mid / High and the "Auto" toggle to Daikin's Auto. The separate
  Fan accessory does the same with a plain slider.
- Turning the Fan accessory off turns the air conditioner off (configurable).
- Home Assistant itself is improving the HomeKit Bridge's fan-mode detection in
  newer releases; the proxy keeps working either way and still provides the
  Fan only / Dry switches and the Auto hiding.

## Development

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements_test.txt
pytest
```
