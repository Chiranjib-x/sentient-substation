# Demo Script — Sentient Substation

Team ERROR 404 · Schneider PredictX Hackathon
**Total runtime: 8 minutes.** 1 min problem · 5 min demo · 2 min business case.

---

## Before you walk in

- [ ] Laptop plugged in, sleep and notifications **off**
- [ ] Server already running — never start it in front of the jury
- [ ] Browser at `http://127.0.0.1:8000`, zoom 100%, full screen (F11)
- [ ] Press **Reset** so you begin from a clean state
- [ ] Video backup of a full run open in a second tab
- [ ] `DEMO.md` (this file) on your phone, not on the projected screen

```
cd "c:\Users\OMEN\Desktop\Schneider Hackathon"
.venv\Scripts\python -m uvicorn api:app
```

**If the server refuses to start**, port 8000 is still held by an old run:

```
netstat -ano | findstr :8000
taskkill /F /PID <the number in the last column>
```

### Who does what

| Person | Role during the pitch |
|---|---|
| **Chiranjib** | Talks. Never touches the laptop. |
| **Rudresh** | Drives the screen. Clicks only when cued. |
| **Bibek** | Answers any physics or standards question. |
| **Vishal** | Answers any software or data question. |

One voice at a time. If a question lands outside your area, say the owner's name and hand it over — a team that routes cleanly looks like a team that has actually worked together.

---

## Part 1 — The problem (60 seconds, no screen)

> "A substation has protective relays whose job is to disconnect a fault. Their settings are
> calculated by hand, in a spreadsheet, over several days — and then left alone for years.
>
> Two things go wrong. Bad settings mean a small fault trips the breaker for a whole
> neighbourhood instead of one street. And separately, the sticker on the panel that tells a
> technician how dangerous that equipment is was calculated once, years ago.
>
> Here is what nobody joins up: **an arc flash's severity depends almost entirely on how long the
> arc burns — and what decides that is the relay setting.** So these are not two problems. They
> are one loop, and today nobody closes it."

Then, and only then, turn to the screen.

---

## Part 2 — The demo (5 minutes)

### Beat 1 · Show what today looks like — 45 s

**Click:** `Copy-paste` → then `Inject fault` (bus already set to `F1 far`)

**Point at:** the banner and the greyed-out sections of the diagram.

> "These are the settings a rushed engineer ships — the same values copied onto every relay.
> Watch what a single fault does.
>
> Two breakers opened, not one. The correct relay cleared it in 143 milliseconds, but the one
> upstream tripped 27 milliseconds later — and a breaker takes 70 milliseconds to physically
> open. So the upstream breaker was already moving. **Three sections went dark when one should
> have.** That is a cascading outage, from one fault, caused purely by arithmetic."

**Also point at:** the Coordination panel — **18 violations** in red.

---

### Beat 2 · Show what good practice costs — 45 s

**Click:** `Hand-graded` → then `Inject fault`

> "Now the settings a careful protection engineer produces — roughly a day of spreadsheet work.
>
> Only the correct breaker opened. The margin is 300 milliseconds instead of 27. Zero violations.
>
> But look at the cost: total clearing time went from 1.09 seconds to 1.89. Safety was bought with
> time — and time, remember, is exactly what burns people."

---

### Beat 3 · Show what we add — 75 s

**Click:** `Optimise` — **it takes about 15 seconds. Keep talking through it.**

> "Every relay has three settings: how much current wakes it, how long it waits, and its curve
> shape — how sharply its reaction time drops as current rises. There are three standard shapes.
>
> A human picks one shape and uses it everywhere, because mixing them means redoing all the
> arithmetic by hand. Across seven relays that is over two thousand combinations. We search them
> in fifteen seconds."

When it lands, **point at the banner and the Mode comparison table**:

> "Still zero violations — same safety rules, checked at both maximum and minimum grid strength,
> which the manual method skips entirely. But 17% faster. And on the low-voltage board where
> technicians actually work, incident energy halved: 2.8 down to 1.3 calories per square
> centimetre."

---

### Beat 4 · The sensing half — 90 s

**Click:** `Inject hotspot`, then keep talking for ~20 seconds while it develops.

> "Separately, we watch the bolted joints inside the switchgear. A joint working loose gains
> resistance, and resistance under load makes heat — so a connection that is failing gets hotter
> long before it faults.
>
> The hard part is that room temperature and load swing every joint by tens of degrees without
> anything being wrong. A fixed temperature limit is therefore either too twitchy or too late.
> So we don't use one. We compare each phase against its own two neighbours, which share the same
> room and the same load."

**Point at:** the temperature chart, where one line separates from the pack.

> "There it is. We flagged that joint at 48 °C — while healthy connections in the same cabinet
> reach 51 °C at peak load. So no fixed threshold could have caught it this early without
> alarming on healthy equipment. And the alert escalates on its own: investigate, then repair,
> then immediate."

---

### Beat 5 · The honest limit, and the fix — 60 s

**Point at:** the MV busbar hazard card — **48 cal/cm², work prohibited**.

> "Now the uncomfortable part, and we'd rather say it than have you find it.
>
> Our medium-voltage busbar is lethal — 48 calories, well past the line where nobody should work
> live. Optimising the settings improved that by 8%. That is not a tuning failure, it is
> structural: the upstream relay **must** wait for the downstream ones to stay coordinated, and
> that waiting is what burns the technician. Coordination alone can never fix this."

**Click:** `Detection`

> "So the platform says exactly what will. A light-sensing arc-flash relay — an arc inside a
> cabinet is never a downstream fault, so it needs no coordination at all and can trip instantly.
>
> 627 milliseconds down to 63. Forty-eight calories down to 4.8. Prohibited becomes Category 2,
> with every coordination margin untouched.
>
> That is the point of the platform: it does not just tune what it can. It tells you where tuning
> stops working and what hardware to buy instead."

---

## Part 3 — Close (2 minutes)

Cover, in this order:

1. **The ROI numbers** — avoided outage hours, audit labour removed, one avoided injury.
2. **Standards, said out loud** — IEC 60909, IEC 60255-151, IEEE C37.112, IEEE 1584, NFPA 70E, NETA. This is what makes you sound like engineers rather than students.
3. **What a real deployment needs** — IEC 61850 integration, certified relay interfaces, field validation. Knowing the gap between prototype and product is a maturity signal, not a weakness.

---

## Questions you will be asked

**"Is this real or simulated?"**
> "The substation is a realistic model, not a real site, and the telemetry comes from a
> physics-based simulator. Everything else is real: fault currents by IEC 60909, relay curves by
> IEC 60255-151, arc-flash energy by IEEE 1584, gear categories by NFPA 70E. Real standards, real
> maths, simulated site."

**"Why no machine learning? Isn't that the theme?"**
> "Protection engineers reject models they cannot audit — that is on Schneider's own problem list.
> Our detection reduces to 'this phase is four degrees hotter than its neighbours and has been for
> ten minutes,' which an engineer can check in their head. ML belongs on top of that layer, not
> instead of it."

**"Your submission says IEEE 1584-2018."**
> "We implement the 2002 empirical model below 15 kV and the Lee method above it, which is what
> IEEE 1584 itself directs you to outside its tested range. The 2018 edition needs coefficient
> tables that only come with the purchased standard, and we were not willing to invent numbers
> behind a safety claim. It is one function to swap once we have the standard."

**"Why is the broken copy-paste setting the fastest one?"**
> "Because speed and selectivity genuinely trade against each other. Copy-paste is fast precisely
> because it doesn't wait — which is why the wrong breaker opens. Our optimiser is the only one of
> the three that improves both at once."

**"How do you know the optimiser's answer is correct?"**
> "It is checked, not trusted. Every primary–backup pair is verified against every fault location
> at both maximum and minimum grid strength, and the check runs as an assertion — the program
> fails loudly rather than shipping a bad setting. We also benchmark against a correct manual
> study, not against the broken one."

**"Would a utility let software change relay settings automatically?"**
> "Not today, and we don't propose it. The platform computes and justifies; a human approves.
> Every recommendation shows its arithmetic on screen for exactly that reason."

**"Does this work on a real, meshed network?"**
> "Our fault-current calculation assumes a radial single-source feeder, which covers most
> distribution substations. Meshed topology needs a different current-distribution method — it's
> documented in the code as a known limit with the upgrade path."

**"How much of this did you write yourselves?"**
> Do not get defensive. The winning answer is to know your own system: any team member should be
> able to open any file and explain any number on screen. Rehearse that.

---

## Know these cold

Someone will ask where a number came from. Have these ready.

| Number | Value | Why |
|---|---|---|
| Coordination time interval | 0.3 s | Covers breaker opening, relay overtravel, and margin |
| Pickup margin | 1.25 × load current | Must not trip on normal load |
| Relay minimum operating time | 20 ms | A relay physically cannot act faster |
| Breaker opening time | 60 ms | Why a 27 ms margin causes a cascade |
| Temperature bands | 3 / 4 / 15 K | NETA thermographic criteria — industry's, not ours |
| Burn threshold | 1.2 cal/cm² | Onset of second-degree burn on bare skin |
| Conductor end temperature | 250 °C | IEC 60909 minimum-current correction |

---

## If something breaks

| Problem | Do this |
|---|---|
| Page won't load | Switch to the video backup tab. Keep talking. Do not debug on stage. |
| Optimise seems stuck | It takes ~15 s. Keep explaining the curve-shape search — that fills the gap by design. |
| Numbers differ slightly from this script | Expected. The optimiser is a randomised search; totals move by a few percent between runs. Quote what is on screen, not what is on paper. |
| A click does nothing | Press **Reset** once and continue from the current beat. |

**Never** open a terminal or an editor in front of the jury. The video backup exists precisely so you never have to.
