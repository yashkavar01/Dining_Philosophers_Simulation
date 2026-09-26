# Dining Philosophers Problem Visualizer

An interactive, browser-based visualizer for the classic Dining
Philosophers problem — built to **actually run** the problem, not animate
it. Five (or up to ten) philosophers are real Python `threading.Thread`
objects contending for real `threading.Lock`-based fork resources. You can
watch the naive strategy genuinely deadlock, and then switch to a
deadlock-free strategy and watch the same threads make real progress.

> **This is not a simulated animation.** Every state change, fork
> acquisition, wait, and deadlock shown in the browser is read live from a
> running Flask server that is itself driving real concurrent threads.
> JavaScript in this project never invents philosopher behaviour — it only
> polls and renders what the Python backend reports.

---

## 1. Project Overview

- **Problem simulated:** the classic Dining Philosophers problem (N
  philosophers, N forks, each philosopher needs both neighbouring forks to
  eat).
- **Concurrency model:** each philosopher is an independent OS-scheduled
  Python thread. Forks are `threading.Lock` objects — the actual mutual
  exclusion primitive, not a simulated flag.
- **Strategies implemented:**
  1. **Naive / Unsafe** — left-fork-then-right-fork, no ordering. Can and
     will deadlock.
  2. **Resource Ordering** (Dijkstra) — always acquire the lower-numbered
     fork first. Provably deadlock-free (eliminates circular wait).
  3. **Waiter / Semaphore** — a counting semaphore admits at most N-1
     philosophers into fork contention at once. Also provably
     deadlock-free (eliminates the possibility of all N holding one fork
     each).
- **Deadlock demonstration:** a "Force Deadlock Demo" button
  deterministically synchronizes all philosophers (via a
  `threading.Barrier`) right after they take their first fork, reliably
  reproducing the textbook worst case instead of hoping for it by chance.
- **Deadlock detection:** a background thread builds a live wait-for graph
  and detects the resulting cycle — the same technique used in real
  resource-allocation-graph deadlock detection.

## 2. Features

- Live circular-table visualization (SVG): philosopher state, fork
  ownership, and "waiting-for" arrows, all redrawn from live backend state.
- Real-time event log (state changes, fork requests/acquisitions/releases,
  blocking, eating, deadlock detected/cleared).
- Start / Pause / Resume / Reset / Step controls.
- Manual **step mode**: advance the simulation one synchronization event
  at a time.
- Adjustable philosopher count (3–10) and simulation speed (0.25×–4×,
  changeable live).
- Strategy switcher with an on-screen explanation of *why* the selected
  strategy is or isn't deadlock-free.
- Metrics panel: meals per philosopher, average/maximum wait time, fork
  acquire attempts, blocked attempts, deadlock detections, fork
  utilization — all computed from real recorded data, never fabricated.
- Session-scoped strategy comparison table, built from completed runs.

## 3. Architecture

```
Browser (HTML/CSS/vanilla JS, polling every 300ms)
        │  HTTP (fetch)
        ▼
Flask API layer (backend/app.py) — thin, no simulation logic
        │
        ▼
Simulator (backend/simulation/simulator.py) — owns lifecycle
        │
        ├── Philosopher threads × N   (real threading.Thread)
        ├── DeadlockDetector thread   (wait-for graph + cycle detection)
        ├── Fork objects × N          (real threading.Lock)
        ├── Strategy object           (naive / ordered / waiter)
        ├── EventLogger               (thread-safe event log)
        └── MetricsCollector          (thread-safe counters)
```

See `docs/architecture.md` for diagrams and a fuller explanation.

## 4. Technologies

- **Backend:** Python 3.10+, Flask, `threading` (Lock, Semaphore, Event,
  Barrier, RLock) — no other concurrency or async framework.
- **Frontend:** HTML5, CSS3, vanilla JavaScript (no build step, no
  framework, no external JS libraries).
- **Testing:** pytest.

No database is used — the simulation is in-memory and single-process by
design; there's nothing here that benefits from persistence.

---

## 5. Installation & Setup (Windows)

These steps assume **Windows** with Python 3.10+ already installed (check
with `python --version` in Command Prompt or PowerShell; get it from
[python.org](https://www.python.org/downloads/) if needed, and make sure
"Add python.exe to PATH" is checked during install).

### 5.1 Get the project

Unzip the project folder anywhere, e.g. `C:\Users\<you>\dining-philosophers`.

### 5.2 Create and activate a virtual environment

Open Command Prompt (or PowerShell) in the project's root folder:

```bat
cd dining-philosophers
python -m venv .venv
.venv\Scripts\activate
```

Your prompt should now be prefixed with `(.venv)`. (PowerShell users: if
activation is blocked by the execution policy, run PowerShell as
Administrator once and execute
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, then retry.)

### 5.3 Install dependencies

```bat
pip install -r backend\requirements.txt
```

(Only `Flask` is required to run the app. For running the test suite,
also install `pip install -r requirements-dev.txt`.)

## 6. How to Run the Backend

```bat
cd backend
python app.py
```

You should see:

```
 * Serving Flask app 'app'
 * Running on http://127.0.0.1:5000
```

Leave this window open — it's your live server, running the actual
philosopher threads.

## 7. How to Open the Frontend

Flask serves the frontend itself, so you do **not** open `index.html`
directly. Instead, open a browser and go to:

```
http://127.0.0.1:5000
```

Click **Start** to launch the simulation with the currently selected
strategy, philosopher count, and speed.

## 8. How to Run the Tests

From the project root (with the virtual environment active):

```bat
pip install -r requirements-dev.txt
pytest tests -v
```

All 28 tests should pass. Expect the run to take roughly 30 seconds — most
tests genuinely run the concurrency engine for a second or two rather than
mocking it, so the pass is meaningful.

## 9. How to Reproduce the Deadlock (for your demo)

1. Start the server and open `http://127.0.0.1:5000`.
2. Leave the strategy dropdown on **Naive (Unsafe)** and click **Start**.
3. (Optional but recommended for a live demo) Move the speed slider to
   around 2×–4× so cycles happen quickly.
4. Click **Force Deadlock Demo**. This synchronizes all philosophers right
   after they each take their first fork.
5. Within a few seconds (usually well under 10s), every philosopher will
   show **WAITING**, every fork will show as held, a red **DEADLOCK
   DETECTED** banner will appear, and the wait-for cycle
   (`P0 → P1 → P2 → P3 → P4 → P0`) will be drawn as arrows on the table.
6. The simulation will **not** recover on its own — that's the point.
   Click **Reset** to clear it.

You can also just click **Start** without the trigger and let it run —
deadlock is *possible* by pure timing in naive mode, but not guaranteed
within a short demo window, which is exactly why the trigger button
exists.

## 10. How to Run the Deadlock-Free Modes

1. Click **Reset** if a run is active.
2. Choose **Resource Ordering** or **Waiter / Semaphore** from the
   strategy dropdown, then **Start**.
3. Watch philosophers continue to cycle through THINKING → HUNGRY →
   (occasionally WAITING briefly) → EATING indefinitely. The metrics panel
   will show meals accumulating for every philosopher, and the deadlock
   banner will never appear.
4. Read the explanation panel under the table for the specific reason that
   strategy cannot deadlock.
5. Click **Reset** to end the run and add a row to the Strategy Comparison
   table at the bottom of the page.

## 11. Known Limitations

- The Flask development server (`app.run(...)`) is used as-is; it is not
  meant for production deployment, only for local demonstration, per the
  project's scope.
- The simulation is single-process and in-memory: refreshing the browser
  does not restart the simulation (state lives in the server, not the
  page), but restarting `app.py` does clear all state.
- Fork "utilization" is measured only for the portion of hold time spent
  actively eating, not time spent holding one fork while blocked on the
  other — this is a deliberate, documented definition (see
  `docs/algorithms.md`), not a bug.
- Manual step mode gates the four major lifecycle transitions (thinking,
  hungry, each fork request, eating) — it does not pause mid-sleep during
  a think/eat interval, since that isn't itself a synchronization event.
- The project targets 3–10 philosophers; going higher would work
  mechanically but the circular visualization gets cramped.
- No authentication, multi-user session separation, or persistence layer
  exists — this is a single-operator local teaching tool, not a
  multi-tenant web service.

## 12. Project Structure

```
dining-philosophers/
├── backend/
│   ├── app.py                       # Flask routes only
│   ├── requirements.txt
│   └── simulation/
│       ├── models.py                # Enums + Event dataclass
│       ├── fork.py                  # Fork = Lock + metadata
│       ├── philosopher.py           # Philosopher thread / state machine
│       ├── strategies.py            # naive / ordered / waiter
│       ├── step_controller.py       # manual step-mode gate
│       ├── deadlock_detector.py     # wait-for graph + cycle detection
│       ├── simulator.py             # lifecycle owner, only class app.py calls
│       ├── metrics.py               # MetricsCollector
│       └── event_logger.py          # thread-safe event log
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── script.js                    # polling + rendering only
├── tests/                           # 28 pytest tests, see docs/architecture.md
├── docs/
│   ├── architecture.md
│   ├── algorithms.md
│   └── viva_questions.md
├── report/
│   └── project_report.md
├── ppt/
│   └── presentation_outline.md
├── requirements-dev.txt
└── README.md
```

---

*All data shown by this visualizer — states, fork ownership, event
timestamps, and metrics — is measured from an actually-running simulation.
Nothing is scripted or pre-recorded.*
