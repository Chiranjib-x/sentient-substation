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
| `arcflash.py` | Bibek | IEEE 1584-2018 incident energy, NFPA 70E PPE mapping |
| `sensors.py` | Vishal | Thermal telemetry simulator, EWMA anomaly detection |
| `api.py` | Vishal | FastAPI, WebSocket push, SQLite log — the only integration point |
| `test_core.py` | all | CTI holds after optimization; lower clearing time ⇒ lower incident energy |
| `ui/` | — | React dashboard (Sprint 3, Sep 8) |

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

Run the tests:

```bash
.venv\Scripts\python test_core.py
```

## Standards

IEC 60255-151 (relay inverse-time curves) · IEC 60909 (short-circuit currents) ·
IEEE C37.112 (inverse-time characteristic equations) · IEEE 1584-2018 (arc-flash incident energy) ·
NFPA 70E (PPE categories)

## Plan

Full phase-wise execution plan with dates, roles, and risks: [PLAN.md](PLAN.md)
