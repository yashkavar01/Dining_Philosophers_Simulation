# Presentation Outline — Dining Philosophers Problem Visualizer

Target: 8–10 slides, 8–10 minute faculty demonstration. Each slide below
lists the content to put on it and a suggested talking point — not a
script. Bring the live app up in a browser tab and switch to it for
Slides 8–9 (marked **[LIVE DEMO]**).

---

**Slide 1 — Title**
- Project title, project number, your name/roll number, course, guide
  name, date.
- One-line subtitle: "A real concurrency engine, not an animation."

**Slide 2 — Problem Statement**
- Official brief: *"Simulate the classic dining philosophers problem with
  a deadlock-free solution."*
- One sentence on why this matters: shared-resource contention and
  deadlock are real OS/systems failure modes, not just a puzzle.

**Slide 3 — Dining Philosophers Concept**
- Simple diagram: N philosophers around a table, N forks between them,
  each philosopher needs both adjacent forks to eat.
- State cycle: THINKING → HUNGRY → (possibly WAITING) → EATING → repeat.

**Slide 4 — Deadlock Scenario**
- The naive rule: left fork first, then right fork.
- The five-line deadlock picture (use the Mermaid diagram from
  `docs/architecture.md` §5): `P0 → P1 → P2 → P3 → P4 → P0`.
- Name the four Coffman conditions in one line each, and point out all
  four are present in this exact scenario.

**Slide 5 — Proposed Solution**
- Two deadlock-free strategies implemented:
  - **Resource Ordering** — always take the lower-numbered fork first;
    removes circular wait.
  - **Waiter / Semaphore** — admit at most N−1 philosophers into
    contention at once; removes full-scale hold-and-wait.
- One line: both are *prevention* (structural), not *avoidance*
  (runtime safe-state check) — and the report explains the distinction.

**Slide 6 — System Architecture**
- Reuse the system architecture diagram from `docs/architecture.md` §1:
  Browser → Flask API → Simulator → Philosopher threads / Fork locks /
  Strategy / Deadlock detector.
- One line: Flask and the frontend are thin — all synchronization logic
  lives in the `simulation/` package, independently testable.

**Slide 7 — Implementation Highlights**
- Real primitives used: `threading.Lock` (forks), `threading.Semaphore`
  (waiter strategy + step mode), `threading.Barrier` (deterministic
  deadlock trigger), `threading.Event` (pause/stop/manual-mode signals).
- One sentence on the poll-with-timeout design and why it keeps
  Pause/Reset responsive without weakening hold-and-wait.
- One sentence on the automated test suite (28 tests: mutual exclusion,
  deadlock reproduction, deadlock prevention, lifecycle correctness).

**Slide 8 — Live Visualization** **[LIVE DEMO — switch to browser]**
- Start the naive strategy, click **Force Deadlock Demo**, let the
  audience watch the DEADLOCK DETECTED banner and circular-wait arrows
  appear from a real, live run.
- Reset, switch to **Resource Ordering** (or **Waiter**), Start again,
  and show continuous progress (meals accumulating, no deadlock banner).

**Slide 9 — Results & Comparison** **[LIVE DEMO, continued]**
- Show the on-page Strategy Comparison table after running all three.
- `[INSERT MEASURED RESULT: your own screenshot of the comparison table
  from this run]`
- Call out explicitly: every number on this table came from the run just
  shown, not from a prepared slide.

**Slide 10 — Conclusion & Future Scope**
- One sentence recap: same threads, same locks, same resources — only
  the acquisition *policy* changed, and that alone was enough to turn a
  permanent deadlock into indefinite progress.
- Future scope (pick 1–2 to mention): a fourth monitor/condition-variable
  ("all-or-nothing" acquisition) strategy; deadlock avoidance via the
  Banker's Algorithm as a contrasting category; a fairness-guaranteeing
  strategy with a starvation-bound test.

---

### Delivery notes
- Rehearse the live-demo slides (8–9) at least once beforehand — set the
  speed slider to 2×–4× before triggering the deadlock demo so it
  resolves within a few seconds on stage.
- Keep Slides 1–7 to roughly 45–60 seconds each; leave 3–4 minutes for
  the live demo (8–9) and question time.
- If the live demo is not possible on presentation day (no network,
  projector issues, etc.), fall back to the screenshots you inserted into
  `report/project_report.md` §13/§15 rather than describing it purely
  verbally.
