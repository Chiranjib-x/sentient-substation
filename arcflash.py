"""Arc-flash incident energy and NFPA 70E PPE category.

This is where the two halves of the platform meet. Incident energy scales directly with
how long the arc burns, and that time is the relay operating time coord.py just chose.
Speed up the relay and the fireball a technician would take gets smaller. Nothing else in
the system couples a protection setting to a human safety outcome this directly.

Two calculation methods, selected by voltage:

  IEEE 1584-2002 empirical model - 208 V to 15 kV, enclosed equipment. Derived from real
      arc-flash test data, so it is the accurate choice inside its validity range.

  Lee method (theoretical maximum) - above 15 kV, or open air. A physics bound rather
      than a fit: it assumes the arc converts the maximum possible power into radiant
      heat. Deliberately pessimistic, and what IEEE 1584 itself directs you to above its
      tested range.

Note on editions: IEEE 1584-2018 replaced the 2002 empirical model with a five-electrode
-configuration model driven by large published coefficient tables. Those tables have to
come from the purchased standard; inventing them would put fabricated numbers behind a
safety claim. The 2002 model implemented here is well documented, still widely used, and
honest about what it is. Swapping in 2018 is a change to one function.

Run directly:  .venv\\Scripts\\python arcflash.py
"""

import math

import coord
import grid

# Enclosure presets: gap between conductors (mm), distance exponent, working distance (mm).
# Working distance is where the worker's face and chest are, not where the arc is.
ENCLOSURES = {
    "LV switchboard": {"gap": 32.0, "x": 1.473, "distance": 610.0, "box": True},
    "LV panelboard": {"gap": 25.0, "x": 1.641, "distance": 455.0, "box": True},
    "MV switchgear": {"gap": 153.0, "x": 0.973, "distance": 910.0, "box": True},
    "open air": {"gap": 153.0, "x": 2.000, "distance": 910.0, "box": False},
}

# Arc-flash protection, as total clearing time in seconds.
#
# Overcurrent relays are graded for selectivity, so upstream relays are deliberately slow -
# precisely where fault energy is highest. That is why coordination tuning alone cannot make
# an MV busbar safe: the incomer MUST wait for the feeder relays, and the waiting is what
# burns the technician.
#
# A light-sensing arc-flash relay escapes the trade-off entirely. An arc inside a switchgear
# cubicle is never a downstream fault, so the relay needs no selectivity and can trip at once
# without breaking any coordination. An arc eliminator goes further, crowbarring the arc into
# a bolted short so the energy stops before the breaker has even moved.
ARC_PROTECTION = {
    "none": None,
    "detection": 0.0025 + 0.06,   # light + current relay, then the breaker opens
    "elimination": 0.004,         # crowbar collapses the arc; no waiting for a breaker
}

IEEE1584_MAX_KV = 15.0   # upper limit of the empirical model's test data
BOUNDARY_CAL = 1.2       # onset of second-degree burn on bare skin, cal/cm2

# NFPA 70E arc-rated clothing categories, by incident energy at the working distance.
PPE_LEVELS = [
    (1.2, 0, "No arc-rated PPE required"),
    (4.0, 1, "Category 1 (4 cal/cm2)"),
    (8.0, 2, "Category 2 (8 cal/cm2)"),
    (25.0, 3, "Category 3 (25 cal/cm2)"),
    (40.0, 4, "Category 4 (40 cal/cm2)"),
]
PROHIBITED = (5, "DANGEROUS - energised work prohibited")


def ppe_category(e_cal):
    """NFPA 70E category for an incident energy in cal/cm2."""
    for limit, idx, label in PPE_LEVELS:
        if e_cal < limit:
            return idx, label
    return PROHIBITED


def ieee1584_2002(v_kv, ibf_ka, t_s, enclosure="LV switchboard", grounded=True):
    """Empirical incident energy in cal/cm2, arc-flash boundary in mm, arcing current kA.

    The arcing current is lower than the bolted fault current - the arc has impedance of
    its own - and it is the arcing current that sets the energy.
    """
    cfg = ENCLOSURES[enclosure]
    gap, x, dist, box = cfg["gap"], cfg["x"], cfg["distance"], cfg["box"]
    lg_ibf = math.log10(ibf_ka)

    if v_kv < 1.0:
        k = -0.097 if box else -0.153
        lg_ia = (k + 0.662 * lg_ibf + 0.0966 * v_kv + 0.000526 * gap
                 + 0.5588 * v_kv * lg_ibf - 0.00304 * gap * lg_ibf)
    else:
        lg_ia = 0.00402 + 0.983 * lg_ibf   # above 1 kV the fit is voltage-independent

    k1 = -0.555 if box else -0.792
    k2 = -0.113 if grounded else 0.0
    en = 10 ** (k1 + k2 + 1.081 * lg_ia + 0.0011 * gap)

    cf = 1.5 if v_kv <= 1.0 else 1.0
    scaled = cf * en * (t_s / 0.2)              # energy at the 610 mm reference distance
    e_cal = scaled * (610.0 / dist) ** x
    boundary = 610.0 * (scaled / BOUNDARY_CAL) ** (1.0 / x)
    return e_cal, boundary, 10 ** lg_ia


def lee(v_kv, ibf_ka, t_s, enclosure="MV switchgear"):
    """Lee theoretical maximum: energy in cal/cm2, boundary in mm.

    Assumes the arc draws maximum power and radiates all of it, with no reduction from
    arc impedance. A bound, not a prediction.
    """
    dist = ENCLOSURES[enclosure]["distance"]
    joules = 5.12e5 * v_kv * ibf_ka * t_s
    return joules / dist ** 2, math.sqrt(joules / BOUNDARY_CAL), ibf_ka


def incident_energy(v_kv, ibf_ka, t_s, enclosure):
    """Pick the defensible method for this voltage, then compute the hazard."""
    if not math.isfinite(t_s):
        # No relay clears this fault at all. The energy is then bounded only by whatever
        # acts next, which is exactly the situation a coordination study exists to prevent.
        return {"method": "NOT CLEARED", "energy_cal": math.inf, "boundary_mm": math.inf,
                "arc_ka": ibf_ka, "clearing_s": t_s}
    if v_kv <= IEEE1584_MAX_KV:
        e, b, ia = ieee1584_2002(v_kv, ibf_ka, t_s, enclosure)
        method = "IEEE 1584-2002"
    else:
        e, b, ia = lee(v_kv, ibf_ka, t_s, enclosure)
        method = "Lee (above 15 kV)"
    return {"method": method, "energy_cal": e, "boundary_mm": b,
            "arc_ka": ia, "clearing_s": t_s}


def hazard_points(net):
    """Where a worker stands, what fault they would face, and which relay saves them.

    `ratio` converts the local fault current into the current the protecting relay
    actually measures. It is 1.0 on the MV side; through the distribution transformer the
    relay sees the LV fault reflected by the turns ratio, which is precisely what makes
    the LV board's safety depend on an MV relay's setting.
    """
    td = net.trafo[net.trafo.name == "TD1"].iloc[0]
    return [
        {"where": "MV busbar", "bus": "MV busbar", "kv": 20.0,
         "enclosure": "MV switchgear", "relay": "Incomer", "ratio": 1.0},
        {"where": "LV switchboard", "bus": "LV switchboard", "kv": 0.4,
         "enclosure": "LV switchboard", "relay": "F1 lateral",
         "ratio": float(td.vn_lv_kv / td.vn_hv_kv)},
    ]


def duties(net, levels=None, weight=3.0):
    """Operating points coord.py must also keep fast: the places people actually stand.

    Zone-end faults are each relay's highest-current case. A fault at an LV board seen
    back through a distribution transformer is a LOW multiple for the MV relay, and an
    optimiser looking only at zone ends will cheerfully pick a curve that is fast there
    and slow here.

    That is not hypothetical. The first working optimiser did exactly this: it satisfied
    every coordination rule and still pushed LV incident energy from 2.8 to 16.0 cal/cm2,
    moving the board from PPE Category 1 to Category 3. Coordination optimisation that
    ignores where humans work can actively endanger them, so the hazard points belong in
    the objective, weighted above equipment-only duty.
    """
    levels = levels if levels is not None else grid.bus_fault_levels(net)
    return [(hp["relay"], levels[hp["bus"]] * hp["ratio"], weight)
            for hp in hazard_points(net)]


def assess(net, settings, levels=None, arc_protection="none"):
    """Incident energy and PPE category at each hazard point, for one set of settings.

    `arc_protection` adds a dedicated arc-flash device alongside the overcurrent relay.
    Whichever acts first sets the arcing time, and the overcurrent grading is untouched -
    which is the whole point: this buys safety without costing selectivity.
    """
    levels = levels if levels is not None else grid.bus_fault_levels(net)
    fast = ARC_PROTECTION.get(arc_protection)
    out = []
    for hp in hazard_points(net):
        ibf = levels[hp["bus"]]
        t = coord._t(settings[hp["relay"]], ibf * hp["ratio"])
        cleared_by = hp["relay"]
        if fast is not None and fast < t:
            t, cleared_by = fast, "arc-flash " + arc_protection
        res = incident_energy(hp["kv"], ibf, t, hp["enclosure"])
        res["category"], res["ppe"] = ppe_category(res["energy_cal"])
        res["cleared_by"] = cleared_by
        out.append({**hp, "bolted_ka": ibf, **res})
    return out


def _show(title, rows):
    print(f"\n=== {title} ===")
    for r in rows:
        print(f"  {r['where']} ({r['kv']} kV, {r['bolted_ka']:.2f} kA bolted)")
        print(f"    cleared by {r['relay']} in {r['clearing_s'] * 1000:.0f} ms  "
              f"[{r['method']}]")
        print(f"    incident energy {r['energy_cal']:.2f} cal/cm2 at "
              f"{ENCLOSURES[r['enclosure']]['distance']:.0f} mm working distance")
        print(f"    arc-flash boundary {r['boundary_mm'] / 1000:.2f} m")
        print(f"    -> {r['ppe']}")


if __name__ == "__main__":
    net = grid.build()
    loads = grid.load_currents(net)

    levels = grid.bus_fault_levels(net)
    tuned, tables, _ = coord.optimize(net, extra_duties=duties(net, levels))
    hand = coord.sequential(net, loads, tables)

    rows_hand = assess(net, hand, levels)
    rows_tuned = assess(net, tuned, levels)

    _show("Hand-graded relay settings", rows_hand)
    _show("Optimised relay settings", rows_tuned)

    print("\n=== What the optimiser bought, in safety terms ===")
    for h, t in zip(rows_hand, rows_tuned):
        drop = h["energy_cal"] - t["energy_cal"]
        print(f"  {h['where']:<16} {h['energy_cal']:7.2f} -> {t['energy_cal']:7.2f} cal/cm2 "
              f"({-100 * drop / h['energy_cal']:+5.1f}%)   "
              f"PPE cat {h['category']} -> {t['category']}")

    # The thesis, as an assertion: less time in the fault is less energy into a person.
    # If this ever fails, the "one control loop" claim is wrong.
    for h, t in zip(rows_hand, rows_tuned):
        assert t["clearing_s"] <= h["clearing_s"] + 1e-9, f"{h['where']}: clearing got slower"
        assert t["energy_cal"] <= h["energy_cal"] + 1e-9, f"{h['where']}: energy rose"

    lv = rows_tuned[1]
    doubled = incident_energy(lv["kv"], lv["bolted_ka"], 2 * lv["clearing_s"],
                              lv["enclosure"])
    assert doubled["energy_cal"] > 1.9 * lv["energy_cal"], \
        "energy must scale with arcing time - that proportionality IS the product thesis"

    print()
    print("=== Adding a dedicated arc-flash device (coordination unchanged) ===")
    for opt in ("none", "detection", "elimination"):
        rows = assess(net, tuned, levels, arc_protection=opt)
        print(f"  {opt:<12} " + " | ".join(
            f"{r['where']}: {r['clearing_s'] * 1000:5.1f} ms, {r['energy_cal']:6.2f} cal/cm2,"
            f" cat {r['category']}" for r in rows))

    mv_none = assess(net, tuned, levels, "none")[0]
    mv_det = assess(net, tuned, levels, "detection")[0]
    assert mv_det["energy_cal"] < mv_none["energy_cal"] / 5, (
        "arc detection must transform MV energy, not nudge it - else it is not worth the hardware")
    assert mv_none["category"] >= 4 and mv_det["category"] <= 2, (
        "the MV busbar should move from prohibited to workable")

    print("OK - incident energy tracks relay clearing time at both hazard points.")
