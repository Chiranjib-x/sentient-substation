"""FastAPI service - the one place the four engines meet.

grid.py gives topology and fault levels. coord.py chooses relay settings. arcflash.py
turns the resulting clearing times into incident energy and a PPE category. sensors.py
streams connection temperatures and flags joints that are degrading. This module owns the
clock, holds the state, and pushes it to the dashboard.

Everything integrates here and nowhere else, so a merge conflict between the physics and
the frontend is impossible by construction.

Run:  .venv\\Scripts\\python -m uvicorn api:app --reload
Then: http://127.0.0.1:8000/docs
"""

import asyncio
import math
import random
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import arcflash
import coord
import grid
import sensors

TICK_S = 0.25       # real seconds between pushes
STEP_MIN = 2.0      # simulated minutes per tick, so a full day runs in about 3 minutes


def clean(obj):
    """JSON has no inf or nan. An uncleared fault is a real state, so map it to null
    rather than letting the serialiser throw."""
    if isinstance(obj, dict):
        return {k: clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [clean(v) for v in obj]
    if isinstance(obj, float) and not math.isfinite(obj):
        return None
    return obj


class State:
    """Live substation state. One instance, rebuilt only on reset."""

    def __init__(self):
        self.net = grid.build()
        self.loads = grid.load_currents(self.net)
        self.levels = grid.bus_fault_levels(self.net)
        prs = grid.pairs(self.net)
        self.tables = {
            "max": (prs, grid.fault_currents(self.net, case="max")),
            "min": (prs, grid.fault_currents(self.net, case="min")),
        }
        # Start on hand-graded settings: that is the honest "before" picture, and it is
        # instant. The optimiser is a deliberate user action, because it takes ~15 s.
        self.settings = coord.sequential(self.net, self.loads, self.tables)
        self.mode = "hand-graded"
        self.arc_protection = "none"
        self.optimising = False

        self.detector = sensors.Detector()
        self.rng = random.Random(0)
        self.t_h = 0.0
        self.degrade = None
        self.alerts = []
        self.clients = set()

    @property
    def hazards(self):
        return arcflash.assess(self.net, self.settings, self.levels, self.arc_protection)

    def relay_rows(self):
        t_max = self.tables["max"][1]
        rows = []
        for r in grid.relays(self.net):
            name = r["name"]
            pickup, tms, curve = self.settings[name]
            zone = self.net.bus.at[r["zone_end"], "name"]
            rows.append({
                "relay": name, "pickup_a": pickup * 1000, "tms": tms, "curve": curve,
                "zone_end": zone,
                "fault_ka": t_max[zone][name],
                "op_time_s": coord._t(self.settings[name], t_max[zone][name]),
            })
        return rows

    def snapshot(self):
        v = coord.violations(self.settings, self.tables)
        return clean({
            "mode": self.mode,
            "arc_protection": self.arc_protection,
            "optimising": self.optimising,
            "hours": self.t_h,
            "relays": self.relay_rows(),
            "violations": [
                {"case": c, "primary": p, "backup": b, "fault": f, "margin_s": m}
                for c, p, b, f, m in v
            ],
            "total_clearing_s": coord.primary_time(self.settings, self.net,
                                                   self.tables["max"][1]),
            "hazards": [
                {k: h[k] for k in ("where", "kv", "bolted_ka", "relay", "method",
                                   "clearing_s", "energy_cal", "boundary_mm",
                                   "category", "ppe", "cleared_by")}
                for h in self.hazards
            ],
            "buses": list(self.net.bus.name),
            "sensors": [sensors.sid_str(s) for s in sensors.SENSOR_IDS],
        })

    def step(self):
        """Advance the clock one tick and return the frame to broadcast."""
        self.t_h = (self.t_h + STEP_MIN / 60.0) % 24.0
        frame = sensors.frame_at(self.t_h, self.degrade, self.rng)
        new_alerts = self.detector.update(frame)

        # A thermal alert on its own is a maintenance ticket. Ranked against what that
        # joint would release if it let go, it becomes a work order with a priority.
        energy_at = {h["where"]: h["energy_cal"] for h in self.hazards}
        for a in new_alerts:
            loc = a["sensor"][0]
            a["location"] = loc
            a["sensor"] = sensors.sid_str(a["sensor"])
            a["energy_cal"] = energy_at.get(loc)
            a["risk"] = (sensors.risk_priority(a["delta_k"], energy_at[loc])
                         if loc in energy_at else None)

        self.alerts = new_alerts
        return clean({
            "hours": frame["hours"],
            "load": frame["load"],
            "ambient_c": frame["ambient_c"],
            "temps": {sensors.sid_str(k): v for k, v in frame["temps"].items()},
            "alerts": new_alerts,
        })


state = State()


async def pump():
    """Drive the clock and push to every connected dashboard."""
    while True:
        frame = state.step()
        for ws in list(state.clients):
            try:
                await ws.send_json(frame)
            except Exception:
                state.clients.discard(ws)
        await asyncio.sleep(TICK_S)


@asynccontextmanager
async def lifespan(_):
    task = asyncio.create_task(pump())
    yield
    task.cancel()


app = FastAPI(title="Sentient Substation", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                   allow_headers=["*"])


@app.get("/api/state")
def get_state():
    return state.snapshot()


@app.get("/api/tcc")
def get_tcc():
    """Time-current curves for the log-log plot, plus the fault levels to mark on it."""
    lo = min(s[0] for s in state.settings.values()) * 1.05
    hi = max(max(v for v in seen.values()) for seen in state.tables["max"][1].values()) * 1.5
    return clean({
        "curves": [
            {"relay": name, "points": coord.curve_points(setting, lo, hi)}
            for name, setting in state.settings.items()
        ],
        "faults": [{"bus": bus, "ka": max(seen.values())}
                   for bus, seen in state.tables["max"][1].items()],
    })


@app.post("/api/inject/hotspot")
def inject_hotspot(sensor: str = "LV switchboard/L2", multiplier: float = 3.0,
                   hours: float = 4.0):
    """Start a joint degrading from now, reaching `multiplier` times its resistance."""
    loc, _, phase = sensor.partition("/")
    sid = (loc, phase)
    if sid not in sensors.SENSOR_IDS:
        return {"error": f"unknown sensor {sensor}",
                "known": [sensors.sid_str(s) for s in sensors.SENSOR_IDS]}
    state.degrade = (sid, state.t_h, state.t_h + hours, multiplier)
    return {"injected": sensor, "multiplier": multiplier, "from_hours": state.t_h}


@app.post("/api/optimize")
async def optimize():
    """Re-coordinate. Runs off the event loop so telemetry keeps streaming meanwhile."""
    if state.optimising:
        return {"status": "already running"}
    state.optimising = True
    try:
        duties = arcflash.duties(state.net, state.levels)
        tuned, _, _ = await asyncio.to_thread(coord.optimize, state.net,
                                              extra_duties=duties)
        before = state.hazards
        state.settings = tuned
        state.mode = "optimised"
        after = state.hazards
        return clean({
            "status": "ok",
            "changed": [
                {"where": b["where"],
                 "clearing_s": [b["clearing_s"], a["clearing_s"]],
                 "energy_cal": [b["energy_cal"], a["energy_cal"]],
                 "category": [b["category"], a["category"]]}
                for b, a in zip(before, after)
            ],
        })
    finally:
        state.optimising = False


@app.post("/api/mode/{mode}")
async def set_mode(mode: str):
    """Switch settings. copy-paste and hand-graded are instant; optimised runs the search.

    Being able to put the broken baseline back on screen matters: the demo is only honest
    if the audience sees what today's practice actually produces.
    """
    if mode == "copy-paste":
        state.settings = coord.baseline(state.loads)
    elif mode == "hand-graded":
        state.settings = coord.sequential(state.net, state.loads, state.tables)
    elif mode == "optimised":
        return await optimize()
    else:
        return {"error": f"unknown mode {mode}",
                "known": ["copy-paste", "hand-graded", "optimised"]}
    state.mode = mode
    return state.snapshot()


@app.post("/api/inject/fault")
def inject_fault(bus: str = "F1 far"):
    """Fault a bus and report which breaker actually opens first.

    The relay that SHOULD clear it is the one whose own zone contains the fault. If a
    backup beats it, the fault is cleared by tripping a bigger slice of the network than
    necessary - that is miscoordination, and it is what turns one fault into an outage.
    """
    if bus not in state.levels:
        return {"error": f"unknown bus {bus}", "known": list(state.levels)}

    idx = grid.bus_by_name(state.net, bus)
    ikss = state.levels[bus]
    seen = grid.currents_for_fault(state.net, idx, ikss)
    should = grid.protecting_relay(state.net, idx)

    ops = []
    for name, cur in seen.items():
        t = coord._t(state.settings[name], cur)
        if math.isfinite(t):
            ops.append({"relay": name, "current_ka": cur, "op_time_s": t,
                        "role": "primary" if name == should else "backup"})
    ops.sort(key=lambda o: o["op_time_s"])

    if not ops:
        return clean({"bus": bus, "ikss_ka": ikss, "should_clear": should,
                      "operates": [], "first": None, "correct": False,
                      "spurious": [], "de_energised": []})

    first = ops[0]
    # Any backup that times out before the leading breaker has finished opening has
    # already tripped too, so its section is lost as well.
    deadline = first["op_time_s"] + coord.BREAKER_S + coord.OVERTRAVEL_S
    spurious = [o["relay"] for o in ops[1:] if o["op_time_s"] < deadline]

    lost = set()
    for name in [first["relay"]] + spurious:
        lost.update(grid.downstream_buses(state.net, name))

    return clean({
        "bus": bus,
        "ikss_ka": ikss,
        "should_clear": should,
        "operates": ops,
        "first": first["relay"],
        "correct": first["relay"] == should and not spurious,
        "spurious": spurious,
        "clearing_s": first["op_time_s"],
        "margin_s": (ops[1]["op_time_s"] - ops[0]["op_time_s"]) if len(ops) > 1 else None,
        "needed_margin_s": coord.BREAKER_S + coord.OVERTRAVEL_S,
        "de_energised": sorted(lost),
    })


@app.post("/api/arc-protection/{mode}")
def set_arc_protection(mode: str):
    """Add or remove a dedicated arc-flash device.

    Deliberately independent of the relay settings: an arc inside a cubicle is never a
    downstream fault, so this device needs no selectivity and changes no coordination
    margin. It is the only thing that makes an MV busbar workable, because grading forces
    the incomer to be slow exactly where the energy is worst.
    """
    if mode not in arcflash.ARC_PROTECTION:
        return {"error": f"unknown option {mode}",
                "known": list(arcflash.ARC_PROTECTION)}
    state.arc_protection = mode
    return state.snapshot()


@app.post("/api/reset")
def reset():
    global state
    state = State()
    return {"status": "reset"}


@app.websocket("/ws")
async def ws(websocket: WebSocket):
    await websocket.accept()
    state.clients.add(websocket)
    await websocket.send_json({"snapshot": state.snapshot()})
    try:
        while True:
            await websocket.receive_text()   # client keepalive; we only push
    except WebSocketDisconnect:
        pass
    finally:
        state.clients.discard(websocket)


# Mounted last so it cannot shadow /api or /ws. Serving the dashboard from the same
# process means no second server, no CORS, and nothing to start on demo day but this.
app.mount("/", StaticFiles(directory="static", html=True), name="static")
