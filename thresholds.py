"""
GPU thermal/power threshold profiles.

Values below are representative operating envelopes for modern datacenter
GPUs (SXM/OAM form factors), not exact vendor spec sheets pulled from a
datasheet. They're realistic enough to drive meaningful alert logic, but if
you're wiring this into a real fleet, replace these with the actual
thresholds from your vendor's management/BMC documentation.

temp_warn_c / temp_crit_c: junction temperature in Celsius
power_warn_w / power_crit_w: board power draw in Watts
tdp_w: rated thermal design power, used to compute % headroom
"""

GPU_PROFILES = {
    "H100-SXM5": {
        "tdp_w": 700,
        "power_warn_w": 630,   # ~90% of TDP
        "power_crit_w": 700,
        "temp_warn_c": 80,
        "temp_crit_c": 88,
    },
    "A100-SXM4": {
        "tdp_w": 400,
        "power_warn_w": 360,
        "power_crit_w": 400,
        "temp_warn_c": 78,
        "temp_crit_c": 85,
    },
    "H100-PCIe": {
        "tdp_w": 350,
        "power_warn_w": 315,
        "power_crit_w": 350,
        "temp_warn_c": 78,
        "temp_crit_c": 84,
    },
}

# Rate-of-change guardrails, independent of absolute thresholds. A GPU
# jumping several degrees or watts in a single tick usually indicates a
# sensor fault or a real event worth flagging even before it crosses the
# absolute threshold.
MAX_TEMP_DELTA_PER_TICK_C = 6.0
MAX_POWER_DELTA_PER_TICK_W = 120.0

# Fan speed is tracked as a percentage of max RPM. Below this while temp is
# climbing indicates a fan degradation / airflow problem, not a GPU problem.
FAN_STALL_PCT = 15.0
