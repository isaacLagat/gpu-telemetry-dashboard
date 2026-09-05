"""
Anomaly detection applied to each new telemetry reading.

Two layers, deliberately kept separate:

1. Absolute threshold checks (thresholds.GPU_PROFILES) — catches sustained
   over-temp / over-power conditions.
2. Rate-of-change checks — catches sudden jumps and sensor glitches that
   wouldn't cross an absolute threshold yet, but are still abnormal.

Both layers matter in practice: a GPU that's been running hot for an hour
and one that just jumped 40 degrees in a single reading are different
problems (thermal management vs. sensor/hardware fault) and should be
flagged differently.
"""

from thresholds import (
    GPU_PROFILES,
    MAX_TEMP_DELTA_PER_TICK_C,
    MAX_POWER_DELTA_PER_TICK_W,
    FAN_STALL_PCT,
)

# last-seen reading per gpu_id, used for rate-of-change checks
_last_reading: dict[str, dict] = {}


def evaluate(reading: dict) -> list[dict]:
    """Returns a list of alert dicts (possibly empty) for this reading."""
    alerts = []
    profile = GPU_PROFILES[reading["gpu_model"]]
    gpu_id = reading["gpu_id"]
    temp_c, power_w, fan_pct = reading["temp_c"], reading["power_w"], reading["fan_pct"]

    # --- Absolute thresholds ---
    if temp_c >= profile["temp_crit_c"]:
        alerts.append(_alert(gpu_id, "critical", f"Temperature {temp_c}°C at/above critical limit {profile['temp_crit_c']}°C", reading))
    elif temp_c >= profile["temp_warn_c"]:
        alerts.append(_alert(gpu_id, "warn", f"Temperature {temp_c}°C above warning threshold {profile['temp_warn_c']}°C", reading))

    if power_w >= profile["power_crit_w"]:
        alerts.append(_alert(gpu_id, "critical", f"Power draw {power_w}W at/above critical limit {profile['power_crit_w']}W", reading))
    elif power_w >= profile["power_warn_w"]:
        alerts.append(_alert(gpu_id, "warn", f"Power draw {power_w}W above warning threshold {profile['power_warn_w']}W", reading))

    if fan_pct <= FAN_STALL_PCT and temp_c > 50:
        alerts.append(_alert(gpu_id, "critical", f"Fan at {fan_pct}% while temperature is {temp_c}°C — possible fan failure", reading))

    # --- Rate-of-change checks ---
    prev = _last_reading.get(gpu_id)
    if prev:
        temp_delta = abs(temp_c - prev["temp_c"])
        power_delta = abs(power_w - prev["power_w"])
        if temp_delta >= MAX_TEMP_DELTA_PER_TICK_C:
            alerts.append(_alert(gpu_id, "warn", f"Temperature jumped {temp_delta:.1f}°C in one sampling interval — check for sensor fault", reading))
        if power_delta >= MAX_POWER_DELTA_PER_TICK_W:
            alerts.append(_alert(gpu_id, "warn", f"Power draw jumped {power_delta:.1f}W in one sampling interval", reading))

    _last_reading[gpu_id] = reading
    return alerts


def _alert(gpu_id: str, severity: str, reason: str, reading: dict) -> dict:
    return {
        "gpu_id": gpu_id,
        "severity": severity,
        "reason": reason,
        "temp_c": reading["temp_c"],
        "power_w": reading["power_w"],
        "fan_pct": reading["fan_pct"],
    }
