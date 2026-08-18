"""Relay curves, coordination checking, and setting optimisation.

Inverse-time overcurrent characteristics per IEC 60255-151 and IEEE C37.112:

    t = TMS * ( K / ((I/Is)^alpha - 1) + B )

Is is the pickup current, TMS the time multiplier. IEC curves have B = 0; the IEEE
form carries a non-zero B. One equation covers both standards.

Coordination rule: for every primary/backup relay pair, and every fault the pair can
both see, the backup must operate at least CTI seconds after the primary. Otherwise the
backup races the primary and trips a healthy feeder, which is how one fault becomes a
cascading outage.

A setting is three numbers, not two: pickup, time multiplier, AND curve shape. alpha
controls how sharply the relay distinguishes a close fault from a distant one, so the
choice of curve is what creates grading headroom. Hand studies pick one family and stick
with it for the whole feeder because varying it means redoing the arithmetic; searching
over it is where this engine actually beats a spreadsheet.

Run directly:  .venv\\Scripts\\python coord.py
"""

import math

import numpy as np
from scipy.optimize import differential_evolution

import grid

# name: (K, alpha, B)
CURVES = {
    "SI": (0.14, 0.02, 0.0),        # IEC standard inverse
    "VI": (13.5, 1.0, 0.0),         # IEC very inverse
    "EI": (80.0, 2.0, 0.0),         # IEC extremely inverse
    "IEEE-MI": (0.0515, 0.02, 0.114),
    "IEEE-VI": (19.61, 2.0, 0.491),
    "IEEE-EI": (28.2, 2.0, 0.1217),
}
TUNABLE = ["SI", "VI", "EI"]  # one standard family; a real relay is ordered per standard

CTI = 0.3           # coordination time interval, seconds
TOL = 1e-6          # CTI is a design minimum; don't fail a pair on float dust
# Inverse-time curves tend to zero at high current multiples, which is a property of the
# equation and not of any real relay: a numeric relay needs tens of milliseconds to
# measure, decide and energise the trip coil. Without this floor the optimiser buys its
# improvement by claiming sub-millisecond operation, and a protection engineer will spot
# that instantly. Set it from the actual relay's published minimum operating time.
T_MIN_OP = 0.02
PICKUP_MIN = 1.25   # pickup must clear load current with margin
PICKUP_MAX = 2.0    # ...but stay sensitive enough to detect real faults
SENSITIVITY = 0.8   # pickup <= 0.8 * smallest fault current the relay must detect
TMS_RANGE = (0.05, 1.0)
DEFAULT_CURVE = "SI"


def op_time(i_ka, pickup_ka, tms, curve=DEFAULT_CURVE):
    """Operating time in seconds. inf if the relay never picks up for this current."""
    K, alpha, B = CURVES[curve]
    m = i_ka / pickup_ka
    if m <= 1.0:
        return math.inf
    return max(tms * (K / (m ** alpha - 1.0) + B), T_MIN_OP)


def _t(setting, current):
    pickup, tms, curve = setting
    return op_time(current, pickup, tms, curve) if current > pickup else math.inf


def violations(settings, tables, cti=CTI):
    """Every (case, primary, backup, fault, margin) where grading fails.

    Checked at maximum AND minimum infeed: settings that grade correctly at full fault
    level can still fail at minimum generation, and that is exactly the condition a
    hand study skips.
    """
    out = []
    for case, (pairs, table) in tables.items():
        for primary, backup in pairs:
            for fault_bus, seen in table.items():
                tp = _t(settings[primary], seen[primary])
                if not math.isfinite(tp):
                    continue  # primary is not responsible for this fault
                margin = _t(settings[backup], seen[backup]) - tp
                if margin < cti - TOL:
                    out.append((case, primary, backup, fault_bus, margin))
    return out


def primary_time(settings, net, table):
    """Total clearing time for in-zone faults — the thing worth minimising.

    Faster primary clearing means less energy into the fault, which is the same number
    arcflash.py turns into incident energy. This objective IS the safety objective.
    """
    total = 0.0
    for r in grid.relays(net):
        t = _t(settings[r["name"]], table[net.bus.at[r["zone_end"], "name"]][r["name"]])
        total += t if math.isfinite(t) else 100.0
    return total


def _pickup_ceiling(name, load_ka, t_min):
    """Highest pickup that still detects the weakest fault this relay answers for."""
    weakest = min((seen[name] for seen in t_min.values() if seen[name] > 0), default=math.inf)
    return min(PICKUP_MAX, SENSITIVITY * weakest / load_ka)


def baseline(loads):
    """What a hurried engineer ships: one pickup rule, one multiplier, copied down.

    Not a strawman — identical multipliers across a feeder is a documented real habit,
    and it is exactly what miscoordinates.
    """
    return {name: (PICKUP_MIN * ka, 0.1, DEFAULT_CURVE) for name, ka in loads.items()}


def sequential(net, loads, tables, cti=CTI):
    """Textbook hand grading: pickup by rule, then TMS from the bottom up, one curve.

    The honest benchmark. Beating the copy-paste baseline proves nothing because it is
    simply wrong; beating a correct manual study is the actual claim. Doubles as the
    fallback if differential_evolution ever stops converging — deterministic, and it
    always terminates.
    """
    K, alpha, B = CURVES[DEFAULT_CURVE]
    t_min = tables["min"][1]

    downstream = {}
    for p, b in grid.pairs(net):
        downstream.setdefault(b, []).append(p)

    settings = {
        name: (min(PICKUP_MIN, _pickup_ceiling(name, ka, t_min)) * ka,
               TMS_RANGE[0], DEFAULT_CURVE)
        for name, ka in loads.items()
    }

    order = [n for n in settings if n not in downstream]
    rest = [n for n in settings if n in downstream]
    while rest:
        ready = [n for n in rest if all(p in order for p in downstream[n])]
        order += ready
        rest = [n for n in rest if n not in ready]

    for name in order:
        if name not in downstream:
            continue
        pu_b = settings[name][0]
        need = TMS_RANGE[0]
        for _, table in tables.values():
            for prim in downstream[name]:
                for seen in table.values():
                    tp, ib = _t(settings[prim], seen[prim]), seen[name]
                    if not math.isfinite(tp) or ib <= pu_b:
                        continue
                    shape = K / ((ib / pu_b) ** alpha - 1.0) + B
                    need = max(need, (tp + cti) / shape)
        settings[name] = (pu_b, min(need, TMS_RANGE[1]), DEFAULT_CURVE)
    return settings


def optimize(net, cti=CTI, seed=0, extra_duties=()):
    """Search pickup, TMS and curve shape per relay: least clearing time, every CTI held.

    `extra_duties` is a list of (relay, current_ka, weight): operating points that must
    also be fast, beyond the zone-end faults. Supply the places where people physically
    stand. Without them the objective only sees each relay's highest-current case and will
    happily choose a curve that is quick there and slow everywhere else - see
    arcflash.duties() for why that is not hypothetical.

    ponytail: penalty method inside differential_evolution, ~15 lines, converges on a
    7-relay radial feeder. Curve choice is an integer variable, which is why this beats
    hand grading at all. If a larger or meshed network stops converging, fall back to
    sequential() — slower settings, but deterministic.
    """
    names = [r["name"] for r in grid.relays(net)]
    loads = grid.load_currents(net)
    t_max = grid.fault_currents(net, case="max")
    t_min = grid.fault_currents(net, case="min")
    prs = grid.pairs(net)
    tables = {"max": (prs, t_max), "min": (prs, t_min)}

    bounds, integrality = [], []
    for name in names:
        hi = max(_pickup_ceiling(name, loads[name], t_min), PICKUP_MIN + 1e-6)
        bounds += [(PICKUP_MIN, hi), TMS_RANGE, (0, len(TUNABLE) - 1)]
        integrality += [False, False, True]

    def unpack(x):
        return {
            name: (x[3 * i] * loads[name], x[3 * i + 1], TUNABLE[int(round(x[3 * i + 2]))])
            for i, name in enumerate(names)
        }

    # Flatten every (pair, fault) constraint into index arrays ONCE. The search evaluates
    # this tens of thousands of times; rebuilding dicts in that loop is what made the
    # first version take minutes instead of seconds.
    at = {n: i for i, n in enumerate(names)}
    pi, bi, ip, ib = [], [], [], []
    for _, table in tables.values():
        for primary, backup in prs:
            for seen in table.values():
                pi.append(at[primary]); bi.append(at[backup])
                ip.append(seen[primary]); ib.append(seen[backup])
    pi, bi = np.array(pi), np.array(bi)
    ip, ib = np.array(ip), np.array(ib)

    load_arr = np.array([loads[n] for n in names])
    own = np.array([t_max[net.bus.at[r["zone_end"], "name"]][r["name"]]
                    for r in grid.relays(net)])
    curve_par = np.array([CURVES[c] for c in TUNABLE])  # rows of (K, alpha, B)

    d_idx = np.array([at[n] for n, _, _ in extra_duties], dtype=int)
    d_cur = np.array([c for _, c, _ in extra_duties], dtype=float)
    d_w = np.array([w for *_, w in extra_duties], dtype=float)

    def times(current, pickup, tms, K, alpha, B):
        with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
            m = current / pickup
            t = np.maximum(tms * (K / (m ** alpha - 1.0) + B), T_MIN_OP)
        return np.where(m > 1.0, t, np.inf)

    def cost(x):
        pu = x[0::3] * load_arr
        tms = x[1::3]
        K, alpha, B = curve_par[x[2::3].astype(int)].T

        tp = times(ip, pu[pi], tms[pi], K[pi], alpha[pi], B[pi])
        tb = times(ib, pu[bi], tms[bi], K[bi], alpha[bi], B[bi])
        # Where the primary never picks up it is not responsible for that fault, so the
        # pair is simply not a constraint. inf - inf would be nan, hence the mask.
        live = np.isfinite(tp)
        margin = np.where(live, tb - np.where(live, tp, 0.0), np.inf)
        penalty = np.maximum(0.0, cti - margin)
        penalty = np.where(np.isfinite(penalty), penalty, 0.0).sum()

        t_own = times(own, pu, tms, K, alpha, B)
        obj = np.where(np.isfinite(t_own), t_own, 100.0).sum()

        if d_idx.size:
            td = times(d_cur, pu[d_idx], tms[d_idx], K[d_idx], alpha[d_idx], B[d_idx])
            obj += (d_w * np.where(np.isfinite(td), td, 100.0)).sum()

        return obj + 100.0 * penalty

    res = differential_evolution(cost, bounds, integrality=np.array(integrality),
                                 seed=seed, tol=1e-6, maxiter=400, popsize=20,
                                 polish=True)
    return unpack(res.x), tables, t_max


def _report(title, settings, net, tables, t_max):
    v = violations(settings, tables)
    print(f"\n=== {title} ===")
    print(f"  {'relay':<12} {'pickup A':>10} {'TMS':>7} {'curve':>6} {'t_own_zone':>12}")
    for r in grid.relays(net):
        name = r["name"]
        pu, tms, curve = settings[name]
        t = _t(settings[name], t_max[net.bus.at[r["zone_end"], "name"]][name])
        print(f"  {name:<12} {pu * 1000:10.1f} {tms:7.3f} {curve:>6} {t:11.3f}s")
    print(f"  total primary clearing time: {primary_time(settings, net, t_max):.3f}s")
    print(f"  CTI violations: {len(v)}")
    for case, p, b, bus, m in v[:4]:
        print(f"    [{case}] {p} -> {b}, fault at {bus}: margin {m:+.3f}s (need {CTI}s)")
    if len(v) > 4:
        print(f"    ... and {len(v) - 4} more")
    return v


if __name__ == "__main__":
    net = grid.build()
    loads = grid.load_currents(net)

    tuned, tables, t_max = optimize(net)
    base = baseline(loads)
    hand = sequential(net, loads, tables)

    v_base = _report("Copy-paste settings (pickup 1.25x load, TMS 0.1, SI everywhere)",
                     base, net, tables, t_max)
    v_hand = _report("Hand-graded settings (textbook sequential study, SI everywhere)",
                     hand, net, tables, t_max)
    v_tuned = _report("Optimised settings (pickup, TMS and curve searched jointly)",
                      tuned, net, tables, t_max)

    # The technical-feasibility claim, as assertions rather than slides.
    assert v_base, "copy-paste baseline should miscoordinate - else nothing to fix"
    assert not v_hand, f"hand grading left {len(v_hand)} violations - benchmark is broken"
    assert not v_tuned, f"optimizer left {len(v_tuned)} CTI violations"

    t_hand = primary_time(hand, net, t_max)
    t_tuned = primary_time(tuned, net, t_max)
    # The business claim: same safety rules, less time in the fault. If this ever fails,
    # the optimizer is not earning its place and sequential() should ship instead.
    assert t_tuned < t_hand, f"optimiser ({t_tuned:.3f}s) no better than hand ({t_hand:.3f}s)"

    print(f"\nOK - copy-paste: {len(v_base)} violations. "
          f"hand-graded: 0 violations, {t_hand:.3f}s. "
          f"optimised: 0 violations, {t_tuned:.3f}s "
          f"({100 * (t_hand - t_tuned) / t_hand:.1f}% faster).")
