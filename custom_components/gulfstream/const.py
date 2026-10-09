"""Constants for the Gulfstream Pool Heater integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "gulfstream"

# Cloud API (reverse-engineered from the GulfStream / CaptouchWiFi mobile app).
API_URL: Final = "https://www.captouchwifi.com/icm/api/call"
# The app's User-Agent. The backend is lenient but we mirror it for good measure.
USER_AGENT: Final = "GulfStream/10010"

# Config entry keys.
CONF_USERNAME: Final = "username"
CONF_PASSWORD: Final = "password"

# Default polling interval (seconds). The device syncs to the cloud on its own
# cadence (a few seconds after a write), so there is no benefit to polling fast.
DEFAULT_SCAN_INTERVAL: Final = 60

MANUFACTURER: Final = "GulfStream"

# --- Register / currentState field map -------------------------------------
#
# ``thermostatGetDetail`` returns a ``currentState`` object whose keys are the
# decoded device registers. ``thermostatSetBlock`` writes raw registers by
# address. By lining up the field order in ``currentState`` against an observed
# block write (startAddress=27, length=7, data=[RSV1, RSV2, 0, 0, 0, 0, MD])
# the following 1-based register addresses were derived:
#
#   27 RSV1  pool heat setpoint   (CONFIRMED: changing it moves the setpoint)
#   28 RSV2  second (spa) setpoint
#   29 RSV3  reserved             (app writes 0)
#   30 FLT   fault/flags          (app writes 0)
#   31 RSFL  reset-filter flag    (app writes 0)
#   32 RSWF  reset-waterflow flag (app writes 0)
#   33 MD    operating mode enum  (0=off, 1=pool heat, 2=spa)
#
# ``MD`` is a mode value, not a boolean. Observed values (looks bitmask-like,
# bits are not contiguous):
#   0 = off        CONFIRMED (device reports MD=0 when switched off)
#   1 = pool heat  CONFIRMED (device reports MD=1 while in pool heat)
#   4 = spa        CONFIRMED (device reports MD=4 when spa selected in the app)
#   (value 2 / other bits unobserved — possibly cool or another function)
#
# When writing a setpoint/mode the app always sends the full 7-register block
# starting at 27, so we replicate that exact behaviour.
REG_SETPOINT_BLOCK_START: Final = 27
REG_SETPOINT_BLOCK_LEN: Final = 7

# currentState field keys.
KEY_SETPOINT: Final = "RSV1"          # pool heat setpoint
KEY_SETPOINT_SPA: Final = "RSV2"      # spa setpoint
KEY_MODE: Final = "MD"                # operating mode enum (see below)
KEY_CURRENT_TEMP: Final = "LCS"       # current water temperature (inferred)
KEY_MIN_SETPOINT: Final = "MNH"       # minimum allowed setpoint
KEY_MAX_SETPOINT: Final = "MXH"       # maximum allowed setpoint
KEY_UNITS: Final = "CF"               # 0 = Fahrenheit, 1 = Celsius (inferred)
KEY_FAULT: Final = "FLT"              # fault flag: 0 = ok, non-zero = fault (inferred)

# Operating-mode enum values written to register 33 (MD).
MODE_OFF: Final = 0        # CONFIRMED
MODE_POOL: Final = 1       # CONFIRMED (pool heat)
MODE_SPA: Final = 4        # CONFIRMED (spa)

# Home Assistant preset names used to pick the active heating mode.
PRESET_POOL: Final = "pool"
PRESET_SPA: Final = "spa"

# Which setpoint register each heating mode uses.
MODE_SETPOINT_KEY: Final = {
    MODE_POOL: KEY_SETPOINT,      # RSV1
    MODE_SPA: KEY_SETPOINT_SPA,   # RSV2
}

# Fallback setpoint limits if the device does not report them.
DEFAULT_MIN_TEMP_F: Final = 50
DEFAULT_MAX_TEMP_F: Final = 104
