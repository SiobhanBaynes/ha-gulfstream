# Gulfstream Pool Heater — Home Assistant integration

A custom [Home Assistant](https://www.home-assistant.io/) integration for
**GulfStream** pool/spa heat pumps that use the **Compass / CaptouchWiFi** Wi-Fi
module (TI SimpleLink based, sold as part #9009093 and similar). It exposes your
heater as a `climate` entity — current water temperature, target setpoint, and
on/off — by talking to the same cloud API the official mobile app uses.

> [!NOTE]
> **This is a cloud integration (`cloud_polling`).** The Wi-Fi module has no
> local control API — it only connects outbound to the vendor cloud (AWS IoT),
> and its link is TLS-pinned, so purely-local control is not possible with the
> stock firmware. This integration reproduces the app's cloud calls to
> `https://www.captouchwifi.com/icm/api/call`. It needs internet access and a
> working GulfStream/Compass account.

## Features

- 🌡️ **Current water temperature** (read)
- 🎯 **Target setpoint** (read/write) with the device's own min/max limits
- 🔌 **On / Off** via HVAC mode (`heat` / `off`)
- 🔁 Polls every 60 seconds; re-authenticates automatically if the token expires
- ⚙️ UI config flow (no YAML)

## Installation

### HACS (recommended)

1. In HACS → **Integrations** → ⋮ → **Custom repositories**, add
   `https://github.com/YOUR_GITHUB_USERNAME/ha-gulfstream` with category
   **Integration**.
2. Install **Gulfstream Pool Heater**, then restart Home Assistant.

### Manual

Copy `custom_components/gulfstream` into your Home Assistant
`config/custom_components/` directory and restart.

## Configuration

**Settings → Devices & Services → Add Integration → Gulfstream Pool Heater**, and
sign in with the same username/password you use in the mobile app. A climate
entity is created for each heater on the account.

## How it works / protocol notes

The module is a TI SimpleLink Wi-Fi chip. Control flows entirely through the
vendor cloud using a small JSON API:

| Action | Purpose |
|--------|---------|
| `login` | returns a session `token` |
| `getPasDevices` | lists devices (`unique_key`, name, online) |
| `thermostatGetDetail` | returns the full `currentState` register map |
| `thermostatSetBlock` | writes a raw register block (`startAddress`, `length`, `data[]`) |

Setpoint and power are written as a 7-register block starting at address 27:

```
data = [RSV1(pool setpoint), RSV2(spa setpoint), 0, 0, 0, 0, MD(mode)]
```

| Reg | Field | Meaning | Confidence |
|----:|-------|---------|------------|
| 27 | `RSV1` | pool heat setpoint | ✅ confirmed |
| 28 | `RSV2` | spa setpoint | ✅ confirmed |
| 29–32 | `RSV3`/`FLT`/`RSFL`/`RSWF` | reset/flag bytes (written as 0) | ✅ confirmed |
| 33 | `MD` | mode: `0` = off, `1` = heat | ⚠️ inferred |
| — | `LCS` | current water temperature | ⚠️ inferred |
| — | `MNH`/`MXH` | min / max setpoint | ✅ confirmed |
| — | `CF` | units: `0` = °F, `1` = °C | ⚠️ inferred |

> [!WARNING]
> The **mode (`MD`)**, **current-temp (`LCS`)** and **units (`CF`)** mappings are
> inferred from observed traffic, not official documentation. Setpoint control is
> confirmed. If on/off behaves unexpectedly for your model, please open an issue
> with a capture of the app toggling the heater — see below.

### Helping extend the register map

To decode additional fields (cool mode, spa/pool switch, fan, schedules), capture
the app's traffic while toggling those controls and open an issue with the
`thermostatSetBlock` payloads you see. Any HTTPS intercepting proxy works
(e.g. mitmproxy); the API is plain JSON and is **not** certificate-pinned.

## Disclaimer

Not affiliated with, endorsed by, or supported by GulfStream or the makers of the
Compass/CaptouchWiFi app. Uses an undocumented API that may change at any time.
Provided as-is under the MIT license. Controlling heating equipment is at your own
risk — mind your equipment's safe operating limits.

## Before you publish this repo

- [ ] Replace `YOUR_GITHUB_USERNAME` in `manifest.json`, `README.md` and `info.md`.
- [ ] Set your name/year in `LICENSE`.
- [ ] (For HACS default inclusion) add the brand to home-assistant/brands and
      ensure the repo has a description, topics, and the validation workflow green.
