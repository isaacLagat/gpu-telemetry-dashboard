# GPU Thermal / Power Telemetry Dashboard

A live-updating dashboard that monitors a simulated GPU fleet (H100-SXM5,
A100-SXM4, H100-PCIe) for thermal and power anomalies, using the same kind
of threshold and rate-of-change logic that matters when you're actually
babysitting dense GPU nodes.

## Why this exists

At high GPU density, small problems escalate fast: degraded airflow,
a stalling fan, or a power delivery issue doesn't just cause a slowdown,
it can cascade into throttling or a hard failure before anyone notices.
This project simulates that environment so the detection logic can be
demonstrated and tested without needing physical hardware or root/driver
access to a real GPU node.

## Architecture

```
telemetry_simulator.py  →  anomaly_detector.py  →  database.py (SQLite)
   (synthetic sensor          (threshold +              ↓
    data per GPU,              rate-of-change      telemetry_service.py
    scripted anomalies)        checks)              (Flask API)
                                                          ↓
                                                   static/ (dashboard UI,
                                                    polls every 2s)
```

- **`telemetry_simulator.py`** — generates realistic per-GPU sensor traces:
  an idle → ramp → sustained load → cooldown cycle, with small noise, plus
  four scripted anomaly types injected at random during sustained load:
  `thermal_creep` (fan degrades, temp climbs), `power_spike` (sudden power
  jump), `fan_stall` (fan drops near zero under load), and `sensor_glitch`
  (a single implausible reading, simulating a bad sensor read).
- **`thresholds.py`** — per-GPU-model warn/critical thresholds for temp and
  power, plus rate-of-change guardrails. These are representative
  datacenter GPU operating envelopes, not exact vendor spec sheets — swap
  in your actual BMC/vendor thresholds for real deployment.
- **`anomaly_detector.py`** — evaluates each new reading against both the
  absolute thresholds and the rate-of-change guardrails, and emits alerts.
- **`database.py`** — SQLite persistence for every reading and every alert,
  so history isn't lost on restart.
- **`telemetry_service.py`** — Flask app that runs the simulation loop in a
  background thread and exposes a small REST API.
- **`static/`** — vanilla JS + Chart.js dashboard, polling the API every
  2 seconds. No build step, no framework.

## Swapping in real hardware

The detection and dashboard layers don't care where readings come from.
To point this at real GPUs instead of the simulator, replace the call to
`telemetry_simulator.tick()` in `telemetry_service.py`'s loop with a
function that reads `nvidia-smi --query-gpu=temperature.gpu,power.draw,fan.speed`
(or your BMC's Redfish telemetry endpoint) and returns the same reading
shape. Everything downstream — thresholds, alerting, storage, dashboard —
works unchanged.

## Running it

```bash
pip install -r requirements.txt
python3 telemetry_service.py
```

Then open **http://localhost:5050**. Readings start at idle and cycle
through load phases every ~15–40 ticks (2 seconds per tick); anomalies are
only injected during sustained load, so give it a minute or two to see one
trigger. All history is written to `telemetry.db` (gitignored).

## API

| Endpoint | Returns |
|---|---|
| `GET /api/telemetry/latest` | Most recent reading per GPU |
| `GET /api/telemetry/history/<gpu_id>` | Last 5 minutes of readings for one GPU |
| `GET /api/alerts` | 30 most recent alerts, newest first |

## Known limitations

- Thresholds are representative, not pulled from a specific vendor
  datasheet — treat them as a starting point, not ground truth.
- The dashboard polls rather than using websockets — simpler to run and
  reason about, at the cost of a small (2s) latency on updates.
- Anomaly injection is scripted/random rather than learned from real
  fleet data — good for demonstrating detection logic, not a substitute
  for a model trained on actual failure history.
- No authentication on the API/dashboard — fine for a local demo, not for
  exposing on a network as-is.

## License

MIT
