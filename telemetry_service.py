"""
GPU telemetry dashboard service.

Runs the synthetic telemetry fleet in a background thread, persists every
reading to SQLite, evaluates each reading against thresholds, and serves
a small REST API + static dashboard.

Run:
    python3 telemetry_service.py
Then open http://localhost:5050 in a browser.
"""

import threading
import time

from flask import Flask, jsonify, send_from_directory

import database
import telemetry_simulator as sim
from anomaly_detector import evaluate

TICK_SECONDS = 2.0

app = Flask(__name__, static_folder="static", static_url_path="")


def _simulation_loop():
    fleet = sim.make_fleet()
    while True:
        for gpu in fleet:
            reading = sim.tick(gpu)
            database.insert_reading(
                reading["gpu_id"], reading["gpu_model"],
                reading["temp_c"], reading["power_w"], reading["fan_pct"],
            )
            for alert in evaluate(reading):
                database.insert_alert(
                    alert["gpu_id"], alert["severity"], alert["reason"],
                    alert["temp_c"], alert["power_w"], alert["fan_pct"],
                )
        time.sleep(TICK_SECONDS)


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/api/telemetry/latest")
def api_latest():
    return jsonify(database.latest_readings())


@app.route("/api/telemetry/history/<gpu_id>")
def api_history(gpu_id):
    return jsonify(database.history(gpu_id, since_seconds=300))


@app.route("/api/alerts")
def api_alerts():
    return jsonify(database.recent_alerts(limit=30))


if __name__ == "__main__":
    database.init_db()
    threading.Thread(target=_simulation_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=5050, debug=False)
