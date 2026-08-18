# Sentient Substation

**Unified Adaptive Protection & Continuous Safety Platform**
Team ERROR 404 · VIT Vellore · Schneider Electric PredictX Hackathon 2026 — Theme 1: Energy Intelligence

---

> Arc-flash incident energy is proportional to **arcing time**, and arcing time is set by **relay
> coordination**. So relay settings and arc-flash safety are not two problems — they are one control
> loop, and today nobody closes it.

**Problem.** Substations rely on static, manual relay calculations and periodic safety audits,
leaving critical grids vulnerable to cascading blackouts and undetected thermal arc-flash hazards.

**What this does.** Thermal telemetry tells us *where* a fault is about to be born. The coordination
engine decides *how fast* it gets cleared. IEEE 1584 turns those two numbers into a live incident
energy and PPE category — replacing the static sticker on the panel door that was calculated five
years ago and has been wrong ever since.

## Layout

| File | Owner | What |
|---|---|---|
| `grid.py` | Bibek | pandapower network, IEC 60909 fault-current sweep, relay pairs |
| `coord.py` | Bibek | IEC 60255-151 curves, CTI check, coordination optimizer |
| `arcflash.py` | Bibek | IEEE 1584-2002 / Lee incident energy, NFPA 70E PPE mapping |
| `sensors.py` | Vishal | Thermal telemetry simulator, differential NETA detection |
| `api.py` | Vishal | FastAPI, WebSocket push, live clock - the only integration point |
| _checks_ | all | each module self-checks in `__main__`; the assertions are the evidence |
| `static/index.html` | Rudresh | Operator dashboard: single-line diagram, TCC curves, thermal trends |

**Rule:** the owner of a file is the only one who edits it. Integration happens in `api.py` and
nowhere else.

## Setup

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt   # Windows
source .venv/bin/activate && pip install -r requirements.txt   # macOS/Linux
```

Verify the environment:

```bash
.venv\Scripts\python grid.py
```

Every module self-checks when run directly - no separate suite, the assertions live next
to the code they defend:

```
python grid.py       topology, load flow, fault currents
python coord.py      copy-paste vs hand-graded vs optimised settings
python arcflash.py   incident energy and PPE category at both hazard points
python sensors.py    thermal detection, false-positive and lead-time checks
```

## Running the platform

```
python -m uvicorn api:app --reload
```

Then open `http://127.0.0.1:8000/docs`. `POST /api/inject/hotspot` starts a joint
degrading, `POST /api/optimize` re-coordinates and reports what it bought in cal/cm2, and
`/ws` streams telemetry and alerts.


## Standards

IEC 60255-151 (relay inverse-time curves) · IEC 60909 (short-circuit currents) ·
IEEE C37.112 (inverse-time characteristic equations) · IEEE 1584-2002 empirical model and
the Lee method (arc-flash incident energy) · NFPA 70E (PPE categories) ·
NETA thermographic criteria (delta-T severity bands)

IEEE 1584-**2018** is not implemented. Its model needs large coefficient tables that come
with the purchased standard, and inventing them would put fabricated numbers behind a
safety claim. The 2002 empirical model is used below 15 kV and the Lee bound above it,
which is what IEEE 1584 itself directs you to outside its tested range.

## Plan

Full phase-wise execution plan with dates, roles, and risks: [PLAN.md](PLAN.md)
