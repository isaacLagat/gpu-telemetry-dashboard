"""
Synthetic GPU telemetry generator.

Why synthetic, not a real nvidia-smi/DCGM feed:
this project is meant to be run and demoed anywhere, without physical GPU
hardware, and without requiring root/driver access. The anomaly-detection
and alerting logic downstream doesn't care where readings come from — swap
`read_real_gpu_sensors()` in for `_tick()` and everything else works
unchanged against real hardware via nvidia-smi, DCGM, or your BMC's Redfish
telemetry endpoint.

Each simulated GPU follows a baseline load curve (idle -> ramp -> sustained
load -> cooldown) with small random noise, punctuated by scripted anomaly
events so the dashboard has something real to catch:

  - thermal_creep:  fan degrades gradually, temp climbs past warn/crit
  - power_spike:    sudden power draw jump (workload change or fault)
  - fan_stall:      fan speed drops to near-zero while under load
  - sensor_glitch:  a single wildly out-of-range reading (bad sensor read)
"""

import random
import time
from dataclasses import dataclass, field

from thresholds import GPU_PROFILES


@dataclass
class GPUState:
    gpu_id: str
    model: str
    temp_c: float = 35.0
    power_w: float = 60.0
    fan_pct: float = 30.0
    load_phase: str = "idle"          # idle, ramp, sustained, cooldown
    ticks_in_phase: int = 0
    active_anomaly: str | None = None
    anomaly_ticks_remaining: int = 0


def _next_phase(state: GPUState) -> str:
    phase_lengths = {"idle": 15, "ramp": 8, "sustained": 40, "cooldown": 10}
    if state.ticks_in_phase < phase_lengths[state.load_phase]:
        return state.load_phase
    order = ["idle", "ramp", "sustained", "cooldown"]
    return order[(order.index(state.load_phase) + 1) % len(order)]


def _target_for_phase(phase: str, tdp_w: float) -> tuple[float, float, float]:
    """Returns (target_temp_c, target_power_w, target_fan_pct) for a load phase."""
    if phase == "idle":
        return 35.0, tdp_w * 0.10, 25.0
    if phase == "ramp":
        return 65.0, tdp_w * 0.70, 55.0
    if phase == "sustained":
        return 75.0, tdp_w * 0.92, 70.0
    return 45.0, tdp_w * 0.25, 40.0  # cooldown


def maybe_start_anomaly(state: GPUState, anomaly_chance: float = 0.015) -> None:
    if state.active_anomaly is not None:
        return
    if state.load_phase != "sustained":
        return  # anomalies are most meaningful under load
    if random.random() < anomaly_chance:
        state.active_anomaly = random.choice(
            ["thermal_creep", "power_spike", "fan_stall", "sensor_glitch"]
        )
        state.anomaly_ticks_remaining = {
            "thermal_creep": 25,
            "power_spike": 1,
            "fan_stall": 15,
            "sensor_glitch": 1,
        }[state.active_anomaly]


def tick(state: GPUState) -> dict:
    """Advance one simulated sampling interval and return the new reading."""
    profile = GPU_PROFILES[state.model]

    state.ticks_in_phase += 1
    new_phase = _next_phase(state)
    if new_phase != state.load_phase:
        state.load_phase = new_phase
        state.ticks_in_phase = 0

    target_temp, target_power, target_fan = _target_for_phase(state.load_phase, profile["tdp_w"])

    # Smooth movement toward phase target, plus small noise, so traces look
    # like real sensor data rather than a step function or pure random walk.
    state.temp_c += (target_temp - state.temp_c) * 0.15 + random.uniform(-0.6, 0.6)
    state.power_w += (target_power - state.power_w) * 0.20 + random.uniform(-8, 8)
    state.fan_pct += (target_fan - state.fan_pct) * 0.25 + random.uniform(-2, 2)

    maybe_start_anomaly(state)

    if state.active_anomaly:
        if state.active_anomaly == "thermal_creep":
            state.fan_pct = max(5.0, state.fan_pct - 4.0)   # fan degrading
            state.temp_c += 1.8                              # temp climbs unchecked
        elif state.active_anomaly == "power_spike":
            state.power_w += profile["tdp_w"] * 0.35
        elif state.active_anomaly == "fan_stall":
            state.fan_pct = random.uniform(0, 8)
            state.temp_c += 1.2
        elif state.active_anomaly == "sensor_glitch":
            state.temp_c += random.choice([-40, 55])  # implausible single-tick jump

        state.anomaly_ticks_remaining -= 1
        if state.anomaly_ticks_remaining <= 0:
            state.active_anomaly = None

    state.temp_c = max(20.0, min(state.temp_c, 110.0))
    state.power_w = max(10.0, min(state.power_w, profile["tdp_w"] * 1.5))
    state.fan_pct = max(0.0, min(state.fan_pct, 100.0))

    return {
        "gpu_id": state.gpu_id,
        "gpu_model": state.model,
        "temp_c": round(state.temp_c, 1),
        "power_w": round(state.power_w, 1),
        "fan_pct": round(state.fan_pct, 1),
        "timestamp": time.time(),
    }


def make_fleet(models: list[str] | None = None) -> list[GPUState]:
    models = models or ["H100-SXM5", "H100-SXM5", "A100-SXM4", "H100-PCIe"]
    return [
        GPUState(gpu_id=f"gpu-{i}", model=model)
        for i, model in enumerate(models)
    ]
