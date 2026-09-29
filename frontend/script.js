/*
 * All rendering here is driven by polling the Flask API (GET /api/state,
 * /api/events, /api/metrics, /api/comparison). This file contains NO
 * concurrency simulation of its own -- no setTimeout/setInterval is used
 * to fake philosopher behaviour. It only displays what the real Python
 * threads on the server are doing.
 */
const NS = "http://www.w3.org/2000/svg";
let lastEventId = -1;
let currentStrategy = "naive";

// ------------------------------------------------------------- API calls --
async function apiPost(path, body) {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  return res.json();
}

async function apiGet(path) {
  const res = await fetch(path);
  return res.json();
}

// ------------------------------------------------------------- table SVG --
function renderTable(state) {
  const container = document.getElementById("table-container");
  const n = state.philosophers.length;

  if (n === 0) {
    container.innerHTML = '<p class="empty-msg">Click <b>Start</b> to begin the simulation.</p>';
    return;
  }

  const size = 480, cx = size / 2, cy = size / 2;
  const philDist = 185, forkDist = 148, philR = 34, forkR = 15;

  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("viewBox", `0 0 ${size} ${size}`);
  svg.setAttribute("width", "100%");
  svg.setAttribute("height", "480");

  const table = document.createElementNS(NS, "circle");
  table.setAttribute("cx", cx);
  table.setAttribute("cy", cy);
  table.setAttribute("r", 108);
  table.setAttribute("class", "table-circle");
  svg.appendChild(table);

  const philPos = [], forkPos = [];
  for (let i = 0; i < n; i++) {
    const a = -Math.PI / 2 + i * (2 * Math.PI / n);
    philPos.push({ x: cx + philDist * Math.cos(a), y: cy + philDist * Math.sin(a) });
  }
  for (let i = 0; i < n; i++) {
    // Fork i is Philosopher i's LEFT fork and Philosopher (i-1)'s RIGHT fork
    // (backend: left = i, right = (i+1) % N) -- so Fork i sits between
    // Philosopher (i-1) and Philosopher i, i.e. at slot (i - 0.5), not (i + 0.5).
    const a = -Math.PI / 2 + (i - 0.5) * (2 * Math.PI / n);
    forkPos.push({ x: cx + forkDist * Math.cos(a), y: cy + forkDist * Math.sin(a) });
  }

  // Waiting-for arrows first, so philosopher/fork nodes render on top.
  state.philosophers.forEach((p) => {
    if (p.state === "WAITING" && p.waiting_for_fork !== null) {
      const inCycle = state.deadlock.detected && state.deadlock.cycle.includes(p.id);
      drawArrow(svg, philPos[p.id], forkPos[p.waiting_for_fork], inCycle);
    }
  });

  state.forks.forEach((f) => {
    const pos = forkPos[f.id];
    const g = document.createElementNS(NS, "g");
    const rect = document.createElementNS(NS, "rect");
    rect.setAttribute("x", pos.x - forkR);
    rect.setAttribute("y", pos.y - forkR);
    rect.setAttribute("width", forkR * 2);
    rect.setAttribute("height", forkR * 2);
    rect.setAttribute("rx", 4);
    const ownerClass = f.held_by === null ? "fork-free" : `owner-${f.held_by % 10}`;
    rect.setAttribute("class", `fork-box ${ownerClass}`);
    g.appendChild(rect);
    g.appendChild(svgText(pos.x, pos.y + 3, `F${f.id}`, "fork-label"));
    svg.appendChild(g);
  });

  state.philosophers.forEach((p) => {
    const pos = philPos[p.id];
    const inCycle = state.deadlock.detected && state.deadlock.cycle.includes(p.id);
    const g = document.createElementNS(NS, "g");
    const circle = document.createElementNS(NS, "circle");
    circle.setAttribute("cx", pos.x);
    circle.setAttribute("cy", pos.y);
    circle.setAttribute("r", philR);
    circle.setAttribute("class", `phil-circle state-${p.state.toLowerCase()}` + (inCycle ? " in-deadlock" : ""));
    g.appendChild(circle);
    g.appendChild(svgText(pos.x, pos.y - 5, `P${p.id}`, "phil-id"));
    g.appendChild(svgText(pos.x, pos.y + 13, p.state, "phil-state"));
    svg.appendChild(g);
  });

  container.innerHTML = "";
  container.appendChild(svg);
}

function svgText(x, y, text, className) {
  const t = document.createElementNS(NS, "text");
  t.setAttribute("x", x);
  t.setAttribute("y", y);
  t.setAttribute("text-anchor", "middle");
  t.setAttribute("class", className);
  t.textContent = text;
  return t;
}

function drawArrow(svg, from, to, inCycle) {
  const line = document.createElementNS(NS, "line");
  // Shorten slightly so the arrowhead doesn't dive under the fork box.
  const dx = to.x - from.x, dy = to.y - from.y;
  const len = Math.sqrt(dx * dx + dy * dy) || 1;
  const shrink = 20;
  line.setAttribute("x1", from.x);
  line.setAttribute("y1", from.y);
  line.setAttribute("x2", to.x - (dx / len) * shrink);
  line.setAttribute("y2", to.y - (dy / len) * shrink);
  line.setAttribute("class", inCycle ? "arrow-deadlock" : "arrow-wait");
  line.setAttribute("marker-end", inCycle ? "url(#arrowhead-deadlock)" : "url(#arrowhead-wait)");
  svg.appendChild(line);
}

// -------------------------------------------------------------- event log --
function renderNewEvents(events) {
  if (!events.length) return;
  const log = document.getElementById("event-log");
  const wasAtBottom = log.scrollTop + log.clientHeight >= log.scrollHeight - 20;

  events.forEach((e) => {
    const row = document.createElement("div");
    row.className = "log-row type-" + e.event_type.toLowerCase();
    row.textContent = `[${e.timestamp.toFixed(3)}s] ${e.message}`;
    log.appendChild(row);
  });
  while (log.children.length > 300) log.removeChild(log.firstChild);
  if (wasAtBottom) log.scrollTop = log.scrollHeight;

  lastEventId = events[events.length - 1].id;
}

function clearEventLog() {
  document.getElementById("event-log").innerHTML = "";
  lastEventId = -1;
}

// ---------------------------------------------------------------- metrics --
function renderMetrics(m) {
  const grid = document.getElementById("metrics-grid");
  const mealsRow = Object.entries(m.meals_eaten).map(([id, c]) => `P${id}:${c}`).join("  ");
  const avgWaitRow = Object.entries(m.avg_wait_time_per_philosopher).map(([id, v]) => `P${id}:${v}s`).join("  ");
  grid.innerHTML = `
    <div><b>Elapsed time</b>${m.elapsed_time}s</div>
    <div><b>Total meals eaten</b>${m.total_meals}</div>
    <div><b>Meals per philosopher</b>${mealsRow || "—"}</div>
    <div><b>Overall avg wait</b>${m.overall_avg_wait_time}s</div>
    <div><b>Overall max wait</b>${m.overall_max_wait_time}s</div>
    <div><b>Avg wait per philosopher</b>${avgWaitRow || "—"}</div>
    <div><b>Fork acquire attempts</b>${m.fork_acquire_attempts}</div>
    <div><b>Blocked attempts</b>${m.blocked_attempts}</div>
    <div><b>Deadlock detections</b>${m.deadlock_detections}</div>
  `;
}

// ------------------------------------------------------------- comparison --
function renderComparison(rows) {
  const tbody = document.querySelector("#comparison-table tbody");
  const emptyMsg = document.getElementById("comparison-empty");
  if (!rows.length) {
    tbody.innerHTML = "";
    emptyMsg.style.display = "block";
    return;
  }
  emptyMsg.style.display = "none";
  tbody.innerHTML = rows.map((r) => `
    <tr>
      <td>${r.strategy}</td>
      <td>${r.num_philosophers}</td>
      <td>${r.deadlock_observed ? "YES" : "no"}</td>
      <td>${r.total_meals}</td>
      <td>${r.overall_avg_wait_time}s</td>
      <td>${r.overall_max_wait_time}s</td>
      <td>${r.blocked_attempts}</td>
      <td>${r.elapsed_time}s</td>
    </tr>
  `).join("");
}

// ----------------------------------------------------------- apply state --
function applyState(state) {
  currentStrategy = state.strategy;

  renderTable(state);

  const statusBadge = document.getElementById("status-badge");
  statusBadge.textContent = state.status.toUpperCase();
  statusBadge.className = "badge " + state.status;

  document.getElementById("strategy-badge").textContent = "Strategy: " + state.strategy;
  document.getElementById("event-count").textContent = "Events: " + state.event_count;
  document.getElementById("strategy-explanation").textContent = state.strategy_explanation || "";

  const banner = document.getElementById("deadlock-banner");
  if (state.deadlock.detected) {
    banner.classList.remove("hidden");
    const cyc = state.deadlock.cycle.map((id) => `P${id}`).join(" → ") + ` → P${state.deadlock.cycle[0]}`;
    document.getElementById("deadlock-cycle").textContent = cyc;
  } else {
    banner.classList.add("hidden");
  }

  document.getElementById("btn-trigger-deadlock").disabled = state.strategy !== "naive" || state.status !== "running";
}

// -------------------------------------------------------------- polling --
async function poll() {
  try {
    const state = await apiGet("/api/state");
    applyState(state);

    const events = await apiGet(`/api/events?since=${lastEventId}`);
    renderNewEvents(events);

    const metrics = await apiGet("/api/metrics");
    renderMetrics(metrics);
  } catch (err) {
    console.error("poll failed:", err);
  }
}

async function refreshComparison() {
  try {
    const rows = await apiGet("/api/comparison");
    renderComparison(rows);
  } catch (err) {
    console.error("comparison refresh failed:", err);
  }
}

// -------------------------------------------------------------- controls --
document.getElementById("btn-start").onclick = async () => {
  clearEventLog();
  await apiPost("/api/simulation/start", {
    num_philosophers: parseInt(document.getElementById("sel-count").value, 10),
    strategy: document.getElementById("sel-strategy").value,
    speed: parseFloat(document.getElementById("rng-speed").value),
    manual: document.getElementById("chk-manual").checked,
  });
  poll();
};

document.getElementById("btn-pause").onclick = () => apiPost("/api/simulation/pause").then(poll);
document.getElementById("btn-resume").onclick = () => apiPost("/api/simulation/resume").then(poll);

document.getElementById("btn-reset").onclick = async () => {
  await apiPost("/api/simulation/reset");
  clearEventLog();
  await poll();
  await refreshComparison();
};

document.getElementById("btn-step").onclick = () => apiPost("/api/simulation/step").then(poll);

document.getElementById("chk-manual").onchange = (e) =>
  apiPost("/api/simulation/manual_mode", { enabled: e.target.checked });

document.getElementById("sel-strategy").onchange = async (e) => {
  clearEventLog();
  await apiPost("/api/simulation/strategy", { strategy: e.target.value });
  poll();
};

document.getElementById("rng-speed").oninput = (e) => {
  document.getElementById("speed-val").textContent = parseFloat(e.target.value).toFixed(2) + "x";
};
document.getElementById("rng-speed").onchange = (e) =>
  apiPost("/api/simulation/speed", { speed: parseFloat(e.target.value) });

document.getElementById("btn-trigger-deadlock").onclick = () => apiPost("/api/deadlock/trigger").then(poll);

// ----------------------------------------------------------------- start --
setInterval(poll, 300);
setInterval(refreshComparison, 3000);
poll();
refreshComparison();
