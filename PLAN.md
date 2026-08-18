# Sentient Substation — Phase-wise Execution Plan

Team ERROR 404 · VIT Vellore · Schneider PredictX Hackathon (Theme 1: Energy Intelligence)
Plan written 2026-08-06. Final demo 2026-09-30. **8 build weeks, 4 people.**

---

## 0. The one-sentence thesis (memorise this — it is your whole pitch)

> Arc-flash incident energy is proportional to **arcing time**, and arcing time is set by **relay
> coordination**. So relay settings and arc-flash safety are not two problems — they are one control
> loop, and today nobody closes it.

Everything below serves that sentence. When a judge asks "why is this one product and not two
projects glued together?", this is the answer:

- Thermal sensors tell you **where** a fault is about to be born (degrading connection).
- The coordination engine decides **how fast** it will be cleared once born.
- IEEE 1584 turns those two numbers into a **live** incident energy / PPE category — the number the
  static NFPA 70E sticker on the panel door got wrong five years ago.

Static label = one number, forever. Ours = a number that moves when the grid moves.

---

## 1. Scope decision up front (read before you build anything)

Your submitted tech stack is a great *ambition list* and a terrible *8-week plan*. Judges score
**30% technical feasibility, 25% innovation, 25% business/ROI, 20% presentation & prototype
quality**. Nothing in there rewards having three databases. Build the spine first; add stack items
only when a demo beat needs them.

### Build now (the spine)

| Layer | Choice | Why |
|---|---|---|
| Grid model | `pandapower`, IEEE 13-bus trimmed to one MV substation | Only sim you need |
| Fault current | pandapower `shortcircuit` (IEC 60909) | Already in the lib |
| Coordination | `scipy.optimize.differential_evolution` + penalty on CTI | Handles the non-convexity, ~40 lines |
| Curves | IEC 60255-151 standard inverse, `t = TMS·K/((I/Is)^α − 1)` | K=0.14, α=0.02 |
| Telemetry | Python generator → FastAPI background task | No broker needed to prove the idea |
| Anomaly | EWMA + rate-of-rise, explainable, thresholded | ML that engineers reject ≠ innovation |
| Arc flash | IEEE 1584-2018 equations + NFPA 70E PPE mapping | The differentiator |
| Storage | SQLite (`sqlite3`, stdlib) | Time series of a demo substation is ~megabytes |
| Dashboard | React + Vite + Recharts + hand-written SVG single-line | SVG with React state ≈ 100 lines |
| Transport | FastAPI WebSocket | One connection, push everything |

### Deferred (say "planned, not built" if asked — that is a legitimate answer)

`MQTT/Mosquitto` · `Modbus TCP` · `IEC 61850 GOOSE` · `TimescaleDB` · `InfluxDB` · `PostgreSQL` ·
`Redis` · `Pyomo/PuLP` · `pymoo/DEAP` · `D3.js` · `Grafana` · `Prometheus` · `Docker Compose`

**Add-when triggers:** MQTT only when real ESP32 hardware appears (Week 6, optional). Postgres only
when SQLite writes block. Docker only in Week 8, purely so the demo can't die on a laptop.

**Do not build the multi-agent "mother AI" layer from your notes (Phases 7–10) until the
deterministic core demos end-to-end.** Then add exactly one thing: an LLM operator-copilot that
*explains* what the deterministic engine decided. An agent that explains a provable decision scores
innovation points. An agent that *makes* the decision loses you the feasibility score, because
protection engineers reject non-deterministic trips — that is literally problem statement #4 on
your own list.

### Repo layout (7 files, keep it that way)

```
sentient-substation/
  grid.py         # pandapower network + fault current sweep
  coord.py        # relay curves, CTI check, optimizer
  sensors.py      # thermal telemetry simulator
  arcflash.py     # IEEE 1584 incident energy + PPE category
  api.py          # FastAPI, WebSocket, in-memory state, SQLite log
  test_core.py    # assert-based checks: CTI holds, E falls when t falls
  ui/             # Vite + React dashboard
```

---

## 2. Roles (4 people, no idle hands)

| Person | Owns | Backup for |
|---|---|---|
| **Bibek (EEE)** | `grid.py`, `coord.py`, `arcflash.py` — all the physics, all the standards | Business case numbers |
| **Vishal (CSE)** | `api.py`, `sensors.py`, anomaly detection, SQLite | Optimizer tuning |
| **Rudresh** | `static/index.html` — dashboard, SVG single-line, TCC plots, alert feed | Demo operation |
| **Chiranjib (lead)** | Integration, mentor comms, pitch deck, business case, demo script | Everything (you're the glue) |

**Rule:** the person who owns a file is the only one who edits it. Integration happens in `api.py`
and nowhere else. This is how a 4-person team avoids merge hell without a process document.

Mentor: Bhabani Shankar Dey — book him **before Aug 21** to sanity-check relay assumptions. One
wrong assumption about CTI or pickup margins invalidates the whole engine, and an EEE faculty member
catches it in ten minutes.

---

## 3. Calendar

### Phase 0 — Lock-in · **Aug 6–7** (2 days, ~3 hrs)

Registration closes **Aug 7, strict**.

- [ ] Confirm the form is submitted and you have the confirmation mail. Nothing else matters today.
- [ ] Create the GitHub repo, private, all 4 as collaborators. Empty `README.md` with the thesis
      sentence from §0 at the top.
- [ ] Create one shared doc: `sources.md`. Every standard, price, and outage statistic you find for
      the next 8 weeks goes in it with a link. You will need citations at the pitch and you will not
      remember where anything came from in September.

*Maps to your notes: pre-Part-A.*

---

### Phase 1 — Research under exam load · **Aug 8–21** (2 weeks, ~6 hrs/week)

Exams Aug 9–16 (Cloud Arch 9th, Sim Systems 10th, AI 11th, DBMS 12th, ACC 13th, CN 14th, Compiler
16th). Screening also runs Aug 10–21, so there is nothing to demo yet. **Deliberately light.** Two
90-minute sessions per week, that is all.

**Your Phases 1–3 (research infrastructure, find flaws, study maintenance procedures) collapse into
this window.** They are reading, not building.

Week of Aug 8 (during exams, reading only):
- [ ] Bibek: pull the IEEE 13-bus feeder data. Read IEC 60255-151 curve constants and IEEE C37.112.
      Write down the standard inverse formula and the three curve types you'll support.
- [ ] Vishal: skim IEEE 1584-2018 — you need the incident energy equation and the arc-flash boundary
      equation, not the whole standard.
- [ ] Chiranjib: collect real numbers for the business case. Target: cost per hour of unplanned
      substation outage, average arc-flash incident cost (medical + OSHA + downtime), engineer-hours
      per manual coordination study, cost of a periodic arc-flash audit. Five credible figures, in
      `sources.md`, with links.

Week of Aug 17 (exams done, ramp up):
- [ ] `pip install pandapower scipy fastapi uvicorn` — get a load flow to run and print bus
      voltages. That's it. Environment proven.
- [ ] Bibek: run a short-circuit calc on the 13-bus, get fault currents at 3 buses. **Milestone: you
      have real numbers to feed an optimizer.**
- [ ] Book the faculty mentor session. Bring: your relay model, your CTI assumption (0.3 s), your
      pickup margin rule. Ask him to break it.
- [ ] Chiranjib: write the 3 questions you'll ask the Schneider mentor in the first check-in.

**Exit criteria:** load flow runs, fault currents exist, five business numbers cited, relay
assumptions validated by faculty.

---

### Phase 2 — Sprint 1: The coordination engine · **Aug 24–31** (Week 1 of official build)

Top 15 announced Aug 24–Sep 4; Schneider mentor ("Electrifier") assigned. Weekly 30-min check-ins
start. *Maps to your Phase 4 (assess grid and optimize).*

**The demo beat you are building:** *"Here are the settings a human wrote. Here is the fault. Watch
the wrong breaker trip. Now watch our engine fix it in four seconds."*

- [ ] `grid.py`: the substation network, a fault-current sweep at each protected zone, and a list of
      primary→backup relay pairs. Hard-code the pairs — there are maybe six.
- [ ] `coord.py`, part 1: curve function `t(I, TMS, Is)` and a `check_cti(settings)` that returns the
      worst miscoordination margin. Test it against a hand-calculated value first.
- [ ] `coord.py`, part 2: optimizer. Minimise `Σ t_primary` subject to `t_backup − t_primary ≥ 0.3 s`
      for every pair, `TMS ∈ [0.05, 1.0]`, `Is ∈ [1.25·I_load, 0.8·I_fault_min]`. Penalty method
      inside `differential_evolution`.
- [ ] `test_core.py`: assert the optimizer's output satisfies every CTI constraint and beats the
      hand-written baseline on total clearing time. **Non-negotiable — this single assert is your
      technical-feasibility evidence.**
- [ ] Matplotlib log-log TCC plot, before vs after. Ugly is fine this week.

**Mentor check-in #1 questions:** Is 0.3 s the CTI Schneider actually uses? What pickup margin above
load current is standard practice? Which relay family should we model?

**Exit criteria:** a script that ingests topology and prints better-than-baseline settings, with a
passing test and a TCC plot showing the fixed coordination.

---

### Phase 3 — Sprint 2: Thermal + arc flash · **Sep 1–7** (Week 2)

*Maps to your Phase 6 (full logic coverage) and the safety half of the problem statement.*

**The demo beat:** *"That connection is 12 °C above its neighbours and climbing. The sticker on this
panel says PPE Category 2. It's wrong — right now it's Category 3."*

- [ ] `sensors.py`: simulate 8 thermal sensors at connection points. Normal drift + load correlation
      + one injectable degrading connection (slow exponential rise). Emit every second.
- [ ] Anomaly layer: EWMA baseline per sensor + rate-of-rise. Flag when a sensor deviates from *its
      neighbours* (differential temperature beats absolute — ambient shifts fool absolute thresholds
      and every engineer in the room knows it).
- [ ] `arcflash.py`: IEEE 1584-2018 incident energy `E` as a function of arcing current, electrode
      config, gap, working distance and **arcing time** — where arcing time comes from `coord.py`.
      Map `E` → NFPA 70E PPE category. Compute the arc-flash boundary.
- [ ] **Close the loop.** Degrading connection → higher fault probability at that node → recompute
      `E` at current relay settings → if PPE category rises, ask `coord.py` for faster settings at
      that zone → show `E` falling back. Second assert in `test_core.py`: shorter clearing time
      produces strictly lower incident energy.
- [ ] `api.py`: FastAPI, WebSocket push, in-memory state, SQLite append log.

**Mentor check-in #2 questions:** Does ArcBlok give absolute or differential temperature? What
electrode configuration should we assume for MV switchgear? Is re-labelling PPE live something
Schneider customers would accept operationally?

**Exit criteria:** the loop in bold above runs end-to-end in a terminal. This is the innovation
claim. Everything after this is presentation.

---

### Phase 4 — Sprint 3: Dashboard + pitch · **Sep 8–10** (Week 3, short — pitch is Sep 11)

*Maps to your Phase 5 (digital twin / operational intelligence) and Phase 7's frontend.*

- [ ] Single-line diagram: static SVG, React state colours breakers (closed/open/tripped) and sensor
      dots (green/amber/red). No D3.
- [ ] Three panels: live TCC curves (Recharts), thermal trends with the anomaly band shaded, alert
      feed with the plain-English reason for each alert.
- [ ] The **"why" panel** — for every recommendation show the arithmetic: current setting, proposed
      setting, CTI margin gained, clearing time saved, incident energy reduced, PPE category change.
      This is your answer to the black-box objection, and it costs one component.
- [ ] Two demo buttons: `Inject Fault` and `Inject Hotspot`. Judges will want to press them.
- [ ] **Rehearse the demo eight times.** Record it as a video backup. Laptops fail on stage.

**Pitch deck, 8 slides:** problem with a real outage cost → the thesis sentence → live demo →
architecture (one diagram) → standards compliance (IEC 60255-151, IEC 60909, IEEE 1584-2018,
NFPA 70E — this is what makes you look like engineers, not students) → ROI table → roadmap →
the ask.

**ROI table** (25% of your score — Chiranjib owns this, build it from `sources.md`):
avoided outage hours × cost/hour + audit labour eliminated + one avoided arc-flash incident,
against a per-substation deployment cost. One honest number beats five invented ones. State your
assumptions on the slide.

---

### Phase 5 — First pitch · **Sep 11–14**

- Sep 11: pitch to Schneider Senior Managers. Lead with the thesis sentence, demo by minute three.
- Immediately after, **write down every question they asked**, verbatim, before you leave the room.
  That list is the entire syllabus for the next two weeks.
- Sep 14: Top 5 announced.

---

### Phase 6 — Buffer + hardening · **Sep 15–20**

Not in the official calendar. Use it anyway — this is where you fix what the pitch exposed.

- [ ] Address the top 3 questions from the panel.
- [ ] *Now* consider the optional layer from your notes' Phases 8–10: an LLM copilot that reads the
      current state and answers "why did you recommend this?" in operator language. It **narrates**;
      it never trips a breaker. Ship it only if the core is rock solid.
- [ ] Optional hardware: ESP32 + MLX90614 on a breadboard, publishing over MQTT. A real sensor on the
      table is worth more in the room than any slide. Only if someone has spare time.

---

### Phase 7 — Final polish · **Sep 21–29** (10-day official window)

*Maps to your Phases 11–13 (simulate the whole product, debug, finalise).*

- [ ] Incorporate senior-manager feedback into the prototype — explicitly, and **say so on a slide**:
      "you told us X, we built X." Panels reward teams that listen.
- [ ] Second substation topology (the 34-bus feeder) to prove generality: *"same engine, different
      grid, zero code changes."* This kills the "you hard-coded your demo" objection.
- [ ] `docker compose up` — one command, whole stack. Insurance for demo day.
- [ ] Freeze code Sep 27. Last two days are rehearsal only.

---

### Phase 8 — Final presentation · **Sep 30**

R&D Leaders. 20% of score is presentation & prototype quality.

- Demo the loop. Show the second topology. Show the ROI. Show the standards list.
- Close on the roadmap: what a real deployment needs (IEC 61850 integration, certified relay
  interfaces, field validation) — proving you know the difference between a prototype and a product
  is a maturity signal, not a weakness.

*Your Phase 14 (real business case, prove gains) lives here.*

---

## 4. Weekly rhythm (Aug 24 onward)

| Day | What |
|---|---|
| Mon | 20-min standup. Each person: shipped / blocked / this week |
| Wed | Schneider mentor check-in (30 min). Send 3 questions the night before |
| Fri | Integration: everything merges, demo runs end-to-end, `test_core.py` passes |
| Sun | Chiranjib updates the deck with the week's result |

**If it doesn't run end-to-end on Friday, it does not exist.** A broken main branch on a Friday is
the only real emergency in this project.

---

## 5. Risks, ranked

| Risk | Mitigation |
|---|---|
| Scope creep into the agent layer | It's Phase 6, optional, narration-only. Written down here so you can't rationalise it in Week 2 |
| Optimizer won't converge on CTI constraints | Fall back to sequential coordination (set the furthest-downstream relay, walk upstream adding CTI). Deterministic, always works, still beats manual |
| Relay physics wrong | Faculty mentor validates before Aug 21. Cheapest possible insurance |
| Exams eat August | Already priced in — Aug 8–21 is 6 hrs/week |
| Demo dies on stage | Recorded video backup from Sep 10, Docker image from Sep 25 |
| Judges ask "is this real or simulated?" | Answer honestly: simulated telemetry, real standards, real optimization math. Then show the ESP32 if you built it |

---

## 6. Definition of done

A judge presses `Inject Hotspot`. The dashboard flags a degrading connection, recomputes incident
energy, shows PPE category rising from 2 to 3, proposes faster relay settings at that zone, shows the
CTI margins still holding across all six primary–backup pairs, and shows incident energy dropping
back under the Category 2 threshold — with every number and its arithmetic visible on screen.

That is the whole product. Everything in this plan exists to make that thirty seconds work.
