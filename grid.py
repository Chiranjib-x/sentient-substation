"""Substation model: topology, load flow, and IEC 60909 fault currents.

Radial MV substation — 110/20 kV infeed, three feeders, two protected sections each.
That gives seven relays and six primary/backup pairs for coord.py to optimise.

    HV ──[T1]── MV busbar ─┬─[F1 head]─ F1 near ─[F1 lateral]─ F1 far
                           ├─[F2 head]─ F2 near ─[F2 lateral]─ F2 far
                           └─[F3 head]─ F3 near ─[F3 lateral]─ F3 far

Run directly to verify the environment:  .venv\\Scripts\\python grid.py
"""

import logging

import networkx as nx
import pandapower as pp
import pandapower.shortcircuit as sc
import pandapower.topology as top

logging.getLogger("pandapower").setLevel(logging.ERROR)  # numba-not-installed chatter

FEEDERS = 3
LINE_TYPE = "NA2XS2Y 1x240 RM/25 12/20 kV"

# IEC 60909 minimum-current calculations correct line resistance to the conductor
# temperature at the end of the short circuit. 250 C is the permissible limit for XLPE
# and gives the lowest fault current, i.e. the most demanding sensitivity check.
# Drop to the 90 C max operating temperature for a less conservative study.
END_TEMP_C = 250


def build():
    """The demo substation. One function, no config file — the topology IS the config."""
    net = pp.create_empty_network(name="Sentient Substation")

    hv = pp.create_bus(net, vn_kv=110, name="HV infeed")
    mv = pp.create_bus(net, vn_kv=20, name="MV busbar")

    # IEC 60909 needs a source impedance, not just a slack bus
    pp.create_ext_grid(net, hv, vm_pu=1.02, s_sc_max_mva=2500, s_sc_min_mva=1800,
                       rx_max=0.1, rx_min=0.1)
    pp.create_transformer(net, hv, mv, std_type="25 MVA 110/20 kV", name="T1")

    for f in range(1, FEEDERS + 1):
        near = pp.create_bus(net, vn_kv=20, name=f"F{f} near")
        far = pp.create_bus(net, vn_kv=20, name=f"F{f} far")
        pp.create_line(net, mv, near, length_km=2.5, std_type=LINE_TYPE, name=f"F{f} head", endtemp_degree=END_TEMP_C)
        pp.create_line(net, near, far, length_km=3.0, std_type=LINE_TYPE, name=f"F{f} lateral", endtemp_degree=END_TEMP_C)
        pp.create_load(net, near, p_mw=1.2, q_mvar=0.4, name=f"F{f} near load")
        pp.create_load(net, far, p_mw=0.8, q_mvar=0.3, name=f"F{f} far load")

    return net


def bus_by_name(net, name):
    return int(net.bus.index[net.bus.name == name][0])


def relays(net):
    """One relay at the sending end of every line, plus the transformer incomer.

    `zone_end` is the far end of the relay's protected section — the worst-case
    fault location it must still detect, which is what sets minimum pickup.
    """
    out = [{"name": "Incomer", "branch": ("trafo", 0), "zone_end": bus_by_name(net, "MV busbar")}]
    for line_idx, line in net.line.iterrows():
        out.append({"name": line["name"], "branch": ("line", line_idx), "zone_end": line["to_bus"]})
    return out


def pairs(net):
    """(primary, backup) relay-name couples. Backup must clear CTI seconds later."""
    out = []
    for f in range(1, FEEDERS + 1):
        out.append((f"F{f} lateral", f"F{f} head"))   # lateral backed up by feeder head
        out.append((f"F{f} head", "Incomer"))          # feeder head backed up by incomer
    return out


def branch_buses(net, relay):
    kind, idx = relay["branch"]
    if kind == "line":
        return int(net.line.at[idx, "from_bus"]), int(net.line.at[idx, "to_bus"])
    return int(net.trafo.at[idx, "hv_bus"]), int(net.trafo.at[idx, "lv_bus"])


def fault_currents(net, case="max"):
    """Current seen by each relay for a three-phase fault at the end of each zone.

    Returns {fault_bus_name: {relay_name: kA}} — the table coord.py optimises against.

    Single infeed, radial network: all fault current flows down one path, so every relay
    on the source->fault path carries the full bus fault level and every other relay
    carries none. Correct by construction, and it sidesteps pandapower's branch-result
    path, which is flagged beta and least reliable exactly where we need it — the
    transformer feeding our incomer relay.

    ponytail: radial + 3ph only. Meshed topology or earth faults => switch to branch
    results (or a proper distribution-factor calc) and re-verify against a hand check.
    """
    sc.calc_sc(net, fault="3ph", case=case)
    ikss_all = net.res_bus_sc.ikss_ka
    graph = top.create_nxgraph(net, respect_switches=False)
    source = int(net.ext_grid.bus.iat[0])

    table = {}
    for bus in sorted({r["zone_end"] for r in relays(net)}):
        path = nx.shortest_path(graph, source, bus)
        energised = set(zip(path, path[1:])) | set(zip(path[1:], path))
        ikss = float(ikss_all.at[bus])
        table[net.bus.at[bus, "name"]] = {
            r["name"]: (ikss if branch_buses(net, r) in energised else 0.0)
            for r in relays(net)
        }
    return table


def load_currents(net):
    """Nominal through-current per relay in kA — the floor for pickup setting.

    Read on the MV side for every relay, including the incomer: fault_currents() reports
    20 kV amps, and a pickup compared against 110 kV amps would be off by the turns ratio.
    """
    pp.runpp(net)
    out = {}
    for r in relays(net):
        kind, idx = r["branch"]
        if kind == "line":
            out[r["name"]] = float(abs(net.res_line.at[idx, "i_from_ka"]))
        else:
            out[r["name"]] = float(abs(net.res_trafo.at[idx, "i_lv_ka"]))
    return out


if __name__ == "__main__":
    net = build()
    pp.runpp(net)

    print("=== Load flow ===")
    for i, bus in net.bus.iterrows():
        print(f"  {bus['name']:<14} {net.res_bus.at[i, 'vm_pu']:.4f} pu")

    assert net.res_bus.vm_pu.between(0.9, 1.1).all(), "bus voltage outside +/-10% — check the model"

    print("\n=== Load currents (relay through-current) ===")
    loads = load_currents(net)
    for name, ka in loads.items():
        print(f"  {name:<14} {ka * 1000:7.1f} A")

    print("\n=== Fault currents, 3ph max (kA seen by each relay) ===")
    table = fault_currents(net)
    names = [r["name"] for r in relays(net)]
    print(f"  {'fault at':<14} " + " ".join(f"{n:>13}" for n in names))
    for bus_name, seen in table.items():
        print(f"  {bus_name:<14} " + " ".join(f"{seen[n]:>13.3f}" for n in names))

    # A fault further down the feeder must be cleared through less current, or the
    # model is wrong and every setting computed from it would be wrong too.
    for f in range(1, FEEDERS + 1):
        near, far = table[f"F{f} near"], table[f"F{f} far"]
        head = f"F{f} head"
        assert near[head] > far[head], f"{head}: fault current did not fall with distance"

    # coord.py picks a pickup between load and fault current; if that window is empty
    # or inverted for any relay, no setting exists and the optimizer would fail obscurely.
    for r in relays(net):
        worst = max(seen[r["name"]] for seen in table.values())
        assert worst > loads[r["name"]] * 1.25, f"{r['name']}: no valid pickup window"

    print(f"\nOK - {len(relays(net))} relays, {len(pairs(net))} primary/backup pairs, "
          f"environment verified.")
