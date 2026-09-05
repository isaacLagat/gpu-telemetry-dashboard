const POLL_MS = 2000;
const charts = {};   // gpu_id -> Chart.js instance
const history = {};  // gpu_id -> {labels: [], temps: [], powers: []}

function severityClass(value, warn, crit) {
  if (value >= crit) return "crit";
  if (value >= warn) return "warn";
  return "ok";
}

// Rough warn/crit lookup mirroring thresholds.py, just for client-side coloring.
const PROFILES = {
  "H100-SXM5": { temp_warn: 80, temp_crit: 88, power_warn: 630, power_crit: 700 },
  "A100-SXM4": { temp_warn: 78, temp_crit: 85, power_warn: 360, power_crit: 400 },
  "H100-PCIe": { temp_warn: 78, temp_crit: 84, power_warn: 315, power_crit: 350 },
};

function ensureCard(reading) {
  if (document.getElementById(`card-${reading.gpu_id}`)) return;

  const container = document.getElementById("gpu-cards");
  const card = document.createElement("div");
  card.className = "gpu-card";
  card.id = `card-${reading.gpu_id}`;
  card.innerHTML = `
    <h3>${reading.gpu_id}</h3>
    <div class="model">${reading.gpu_model}</div>
    <div class="metric-row"><span>Temp</span><span class="value" data-field="temp_c">--°C</span></div>
    <div class="metric-row"><span>Power</span><span class="value" data-field="power_w">-- W</span></div>
    <div class="metric-row"><span>Fan</span><span class="value" data-field="fan_pct">--%</span></div>
    <canvas id="chart-${reading.gpu_id}"></canvas>
  `;
  container.appendChild(card);

  history[reading.gpu_id] = { labels: [], temps: [], powers: [] };

  const ctx = document.getElementById(`chart-${reading.gpu_id}`).getContext("2d");
  charts[reading.gpu_id] = new Chart(ctx, {
    type: "line",
    data: {
      labels: [],
      datasets: [
        { label: "Temp °C", data: [], borderColor: "#f5a623", tension: 0.3, pointRadius: 0 },
        { label: "Power W", data: [], borderColor: "#3ddc84", tension: 0.3, pointRadius: 0, yAxisID: "y2" },
      ],
    },
    options: {
      animation: false,
      responsive: true,
      scales: {
        x: { display: false },
        y: { display: false },
        y2: { display: false, position: "right" },
      },
      plugins: { legend: { display: false } },
    },
  });
}

function updateCard(reading) {
  ensureCard(reading);
  const profile = PROFILES[reading.gpu_model] || {};
  const card = document.getElementById(`card-${reading.gpu_id}`);

  const tempEl = card.querySelector('[data-field="temp_c"]');
  tempEl.textContent = `${reading.temp_c}°C`;
  tempEl.className = `value ${severityClass(reading.temp_c, profile.temp_warn, profile.temp_crit)}`;

  const powerEl = card.querySelector('[data-field="power_w"]');
  powerEl.textContent = `${reading.power_w} W`;
  powerEl.className = `value ${severityClass(reading.power_w, profile.power_warn, profile.power_crit)}`;

  const fanEl = card.querySelector('[data-field="fan_pct"]');
  fanEl.textContent = `${reading.fan_pct}%`;
  fanEl.className = `value ${reading.fan_pct < 15 ? "crit" : "ok"}`;

  const h = history[reading.gpu_id];
  h.labels.push("");
  h.temps.push(reading.temp_c);
  h.powers.push(reading.power_w);
  if (h.labels.length > 60) { h.labels.shift(); h.temps.shift(); h.powers.shift(); }

  const chart = charts[reading.gpu_id];
  chart.data.labels = h.labels;
  chart.data.datasets[0].data = h.temps;
  chart.data.datasets[1].data = h.powers;
  chart.update("none");
}

function renderAlerts(alerts) {
  const list = document.getElementById("alerts-list");
  list.innerHTML = "";
  if (alerts.length === 0) {
    list.innerHTML = '<li style="color: var(--muted)">No alerts yet.</li>';
    return;
  }
  for (const a of alerts) {
    const li = document.createElement("li");
    const time = new Date(a.timestamp * 1000).toLocaleTimeString();
    li.innerHTML = `
      <span class="badge ${a.severity}">${a.severity}</span>
      <span>${a.gpu_id}: ${a.reason}</span>
      <span class="alert-time" style="margin-left:auto">${time}</span>
    `;
    list.appendChild(li);
  }
}

async function poll() {
  try {
    const [latestRes, alertsRes] = await Promise.all([
      fetch("/api/telemetry/latest"),
      fetch("/api/alerts"),
    ]);
    const latest = await latestRes.json();
    const alerts = await alertsRes.json();

    latest.forEach(updateCard);
    renderAlerts(alerts);

    document.getElementById("status-pill").textContent = "live";
  } catch (e) {
    document.getElementById("status-pill").textContent = "disconnected";
  }
}

poll();
setInterval(poll, POLL_MS);
