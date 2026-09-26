"""
Flask API layer. Deliberately thin: every route just calls a method on the
single global Simulator instance and returns its snapshot. No
synchronization logic, no thread creation, and no simulation state lives
in this file -- that separation is what keeps the concurrency engine
independently testable (see tests/) without ever starting a web server.

Run with `python app.py` from inside backend/. Serves the frontend AND the
API from one process on http://127.0.0.1:5000, so there is no CORS
configuration to worry about.
"""
from flask import Flask, jsonify, request, send_from_directory
import os

from simulation.simulator import Simulator

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(os.path.dirname(BACKEND_DIR), "frontend")

app = Flask(__name__, static_folder=None)
sim = Simulator()


# --------------------------------------------------------------- frontend --
@app.route("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/<path:filename>")
def static_files(filename):
    return send_from_directory(FRONTEND_DIR, filename)


# -------------------------------------------------------- simulation API --
@app.route("/api/simulation/start", methods=["POST"])
def start():
    body = request.get_json(silent=True) or {}
    try:
        sim.start(
            num_philosophers=body.get("num_philosophers", 5),
            strategy=body.get("strategy", "naive"),
            speed=body.get("speed", 1.0),
            manual=bool(body.get("manual", False)),
        )
    except (ValueError, TypeError) as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(sim.state_snapshot())


@app.route("/api/simulation/pause", methods=["POST"])
def pause():
    sim.pause()
    return jsonify(sim.state_snapshot())


@app.route("/api/simulation/resume", methods=["POST"])
def resume():
    sim.resume()
    return jsonify(sim.state_snapshot())


@app.route("/api/simulation/reset", methods=["POST"])
def reset():
    sim.reset()
    return jsonify(sim.state_snapshot())


@app.route("/api/simulation/step", methods=["POST"])
def step():
    sim.step()
    return jsonify(sim.state_snapshot())


@app.route("/api/simulation/manual_mode", methods=["POST"])
def manual_mode():
    body = request.get_json(silent=True) or {}
    sim.set_manual_mode(bool(body.get("enabled", False)))
    return jsonify(sim.state_snapshot())


@app.route("/api/simulation/speed", methods=["POST"])
def set_speed():
    body = request.get_json(silent=True) or {}
    try:
        sim.set_speed(body.get("speed", sim.speed))
    except (TypeError, ValueError):
        return jsonify({"error": "speed must be a number"}), 400
    return jsonify(sim.state_snapshot())


@app.route("/api/simulation/strategy", methods=["POST"])
def strategy():
    body = request.get_json(silent=True) or {}
    try:
        sim.change_strategy(body.get("strategy"))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(sim.state_snapshot())


@app.route("/api/deadlock/trigger", methods=["POST"])
def trigger_deadlock():
    ok = sim.trigger_deadlock()
    if not ok:
        return jsonify({"error": "Deadlock demo requires the naive strategy to be running."}), 400
    return jsonify(sim.state_snapshot())


# ------------------------------------------------------------- read-only --
@app.route("/api/state", methods=["GET"])
def state():
    return jsonify(sim.state_snapshot())


@app.route("/api/events", methods=["GET"])
def events():
    since = request.args.get("since", default=-1, type=int)
    return jsonify(sim.events.get_since(since))


@app.route("/api/metrics", methods=["GET"])
def metrics():
    return jsonify(sim.metrics.snapshot())


@app.route("/api/comparison", methods=["GET"])
def comparison():
    return jsonify(sim.get_comparison())


if __name__ == "__main__":
    # debug=False is deliberate: Flask's debug reloader spawns a second
    # process, which would create a second, out-of-sync Simulator and
    # duplicate the philosopher threads. threaded=True lets the browser's
    # polling GETs be served without queuing behind each other.
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True)
