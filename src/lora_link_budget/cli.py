"""Command-line front end: `python -m lora_link_budget <command> ...`."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from .airtime import airtime
from .battery import NodeProfile, battery_life
from .linkbudget import LinkBudget, sensitivity_dbm
from .pathloss import Hata, PathLossModel, free_space, log_distance
from .regions import REGIONS, duty_cycle_check

SF_CHOICES = range(7, 13)

# (flag, default, help) for the radio path and the path-loss model; reused by budget and range.
RF_FLAGS = [
    ("--tx-power", 14.0, "dBm at the connector"),
    ("--tx-gain", 2.0, "node antenna gain, dBi"),
    ("--tx-cable", 0.5, "node cable loss, dB"),
    ("--rx-gain", 2.0, "gateway antenna gain, dBi"),
    ("--rx-cable", 0.5, "gateway cable loss, dB"),
    ("--fade-margin", 10.0, "required margin, dB"),
    ("--noise-figure", 6.0, "receiver NF, dB"),
    ("--extra-loss", 0.0, "vegetation / walls, dB"),
    ("--exponent", 3.0, "log-distance exponent n"),
    ("--gw-height", 10.0, "gateway antenna height, m (Hata)"),
    ("--node-height", 1.5, "node antenna height, m (Hata)"),
]
BATTERY_FLAGS = [
    ("--capacity", 2400.0, "battery capacity, mAh"),
    ("--sleep-ma", NodeProfile.sleep_current_ma, "sleep current, mA"),
    ("--active-ma", NodeProfile.active_current_ma, "awake current, mA"),
    ("--active-ms", NodeProfile.active_ms, "awake time per cycle, ms"),
    ("--tx-ma", NodeProfile.tx_current_ma, "transmit current, mA"),
    ("--rx-ma", NodeProfile.rx_current_ma, "receive current, mA"),
    ("--rx-ms", NodeProfile.rx_ms, "receive-window time per cycle, ms"),
]


def _model(a: argparse.Namespace) -> PathLossModel:
    f = REGIONS[a.region].frequency_mhz
    if a.model == "free-space":
        return free_space(f)
    if a.model == "hata":
        return Hata(f, a.gw_height, a.node_height, a.environment)
    return log_distance(f, a.exponent)


def _budget(a: argparse.Namespace) -> LinkBudget:
    return LinkBudget(a.tx_power, a.tx_gain, a.tx_cable, a.rx_gain, a.rx_cable,
                      a.fade_margin, a.noise_figure, a.extra_loss)  # fmt: skip


def _emit(rows: list[dict], a: argparse.Namespace, header: str, notes: set[str] = frozenset()):
    if a.json:
        print(json.dumps(rows, indent=2))
        return
    print(header)
    keys = list(rows[0])
    widths = {k: max(len(k), *(len(str(r[k])) for r in rows)) for k in keys}
    print("  ".join(k.ljust(widths[k]) for k in keys))
    for r in rows:
        print("  ".join(str(r[k]).ljust(widths[k]) for k in keys))
    for n in sorted(notes):
        print("note:", n, file=sys.stderr)


def cmd_airtime(a: argparse.Namespace) -> None:
    bw = REGIONS[a.region].bandwidth_hz
    rows = []
    for sf in a.sf:
        r = airtime(a.payload, sf, bw, lorawan=not a.raw)
        rows.append({"SF": sf, "PHY bytes": r.phy_payload_bytes, "symbols": r.payload_symbols,
                     "T_sym ms": f"{r.symbol_time_ms:.3f}", "LDRO": r.low_data_rate_optimisation,
                     "airtime ms": f"{r.total_ms:.1f}"})  # fmt: skip
    kind = "PHY" if a.raw else "application"
    _emit(rows, a, f"{a.payload}-byte {kind} payload, {bw // 1000} kHz")


def cmd_budget(a: argparse.Namespace) -> None:
    budget, model, bw = _budget(a), _model(a), REGIONS[a.region].bandwidth_hz
    rows, notes = [], set()
    for sf in a.sf:
        r = budget.evaluate(model, a.distance, sf, bw)
        notes.update(r.warnings)
        rows.append({"SF": sf, "sensitivity dBm": f"{r.sensitivity_dbm:.1f}",
                     "path loss dB": f"{r.path_loss_db:.1f}", "RX dBm": f"{r.rx_power_dbm:.1f}",
                     "margin dB": f"{r.margin_db:.1f}", "OK": r.ok})  # fmt: skip
    _emit(rows, a, f"EIRP {budget.eirp_dbm:.1f} dBm, {model.name}, {a.distance:g} m, "
          f"fade margin {budget.fade_margin_db:g} dB", notes)  # fmt: skip


def cmd_range(a: argparse.Namespace) -> None:
    budget, model, bw = _budget(a), _model(a), REGIONS[a.region].bandwidth_hz
    rows, notes = [], set()
    for sf in a.sf:
        mpl = budget.max_path_loss_db(sf, bw)
        d = model.distance_m(mpl)
        notes.update(model.warnings(d))
        rows.append({"SF": sf, "sensitivity dBm": f"{sensitivity_dbm(sf, bw, a.noise_figure):.1f}",
                     "max path loss dB": f"{mpl:.1f}", "range m": f"{d:.0f}"})  # fmt: skip
    _emit(rows, a, f"EIRP {budget.eirp_dbm:.1f} dBm, {model.name}, "
          f"fade margin {budget.fade_margin_db:g} dB", notes)  # fmt: skip


def cmd_dutycycle(a: argparse.Namespace) -> None:
    region = REGIONS[a.region]
    rows = []
    for sf in a.sf:
        t = airtime(a.payload, sf, region.bandwidth_hz).total_ms
        d = duty_cycle_check(region, t, a.per_hour, sf, a.payload)
        m = d.max_messages_per_hour
        rows.append({"SF": sf, "airtime ms": f"{t:.1f}", "duty": f"{d.utilisation:.3%}",
                     "max msg/h": "-" if m is None else f"{m:.0f}",
                     "s/day": f"{d.airtime_per_day_s:.1f}", "TTN fair use": d.ttn_fair_use_ok,
                     "OK": d.ok, "problems": "; ".join(d.problems)})  # fmt: skip
    _emit(rows, a, f"{region.name}: {a.payload} bytes, {a.per_hour:g} messages/hour. {region.note}")


def cmd_battery(a: argparse.Namespace) -> None:
    region = REGIONS[a.region]
    profile = NodeProfile(a.sleep_ma, a.active_ma, a.active_ms, a.tx_ma, a.rx_ma, a.rx_ms)
    rows = []
    for sf in a.sf:
        t = airtime(a.payload, sf, region.bandwidth_hz).total_ms
        b = battery_life(a.capacity, t, a.per_hour, profile)
        rows.append({"SF": sf, "airtime ms": f"{t:.1f}", 
                     "avg uA": f"{b.average_current_ma * 1e3:.1f}",
                     "TX share": f"{b.tx_share:.0%}", "life days": f"{b.life_days:.0f}",
                     "life years": f"{b.life_years:.2f}"})  # fmt: skip
    _emit(rows, a, f"{a.capacity:g} mAh, {a.payload} bytes every {60 / a.per_hour:g} min, "
          f"sleep {a.sleep_ma * 1e3:g} uA, TX {a.tx_ma:g} mA "
          "(80 % usable, 3 %/year self-discharge)")  # fmt: skip


def cmd_example(a: argparse.Namespace) -> None:
    """Farm-scale worked example: nodes on hives / a poultry house, gateway at the farmhouse."""
    print("Worked example: 12-byte uplink every 10 min, EU868, 14 dBm, 2 dBi antennas, 0.5 dB "
          "cable each end,\n10 dB fade margin, gateway 10 m up, nodes at 1.5 m, log-distance n=3 "
          "(flat farmland with crops and trees).\n")  # fmt: skip
    traffic = ["--payload", "12", "--per-hour", "6"]
    for cmd in (["range", "--model", "log-distance"],
                ["range", "--model", "hata", "--environment", "open"],
                ["budget", "--distance", "1500", "--model", "log-distance"],
                ["dutycycle", *traffic], ["battery", "--capacity", "2400", *traffic]):  # fmt: skip
        print(f"$ lora-link-budget {' '.join(cmd)}")
        main(cmd)
        print()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="lora-link-budget", description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)

    def add(name: str, fn, help_: str, flags=()) -> argparse.ArgumentParser:
        sp = sub.add_parser(name, help=help_)
        sp.set_defaults(fn=fn)
        sp.add_argument("--sf", type=int, nargs="+", choices=SF_CHOICES, default=list(SF_CHOICES))
        sp.add_argument("--region", choices=REGIONS, default="EU868")
        sp.add_argument("--json", action="store_true")
        for flag, default, help_text in flags:
            sp.add_argument(flag, type=float, default=default, help=f"{help_text} [{default:g}]")
        return sp

    sp = add("airtime", cmd_airtime, "time on air per spreading factor")
    sp.add_argument("--payload", type=int, default=12, help="bytes")
    sp.add_argument("--raw", action="store_true", help="payload is the PHY payload, no overhead")
    for name, fn, help_ in (("budget", cmd_budget, "received power and margin at a distance"),
                            ("range", cmd_range, "max distance keeping the margin")):  # fmt: skip
        sp = add(name, fn, help_, RF_FLAGS)
        sp.add_argument("--model", choices=["free-space", "log-distance", "hata"],
                        default="log-distance")  # fmt: skip
        sp.add_argument("--environment", choices=["urban", "suburban", "open"], default="open")
        if name == "budget":
            sp.add_argument("--distance", type=float, required=True, help="metres")
    for name, fn, help_, flags in (
        ("dutycycle", cmd_dutycycle, "EU868 duty cycle / US915 dwell-time check", ()),
        ("battery", cmd_battery, "battery life estimate", BATTERY_FLAGS)):  # fmt: skip
        sp = add(name, fn, help_, flags)
        sp.add_argument("--payload", type=int, default=12, help="application bytes")
        sp.add_argument("--per-hour", type=float, default=6.0, help="messages per hour")
    sub.add_parser("example", help="farm-scale worked example (all of the above)").set_defaults(
        fn=cmd_example)  # fmt: skip
    return p


def main(argv: Sequence[str] | None = None) -> None:
    a = build_parser().parse_args(argv)
    a.fn(a)
