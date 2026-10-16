"""Battery life of a sleep / wake / measure / transmit / listen node.

Average current = (sum of charge per cycle) / period + sleep current. The defaults are
illustrative values for an ESP32 + SX1276 class node; measure your own board, because sleep
current and sensor warm-up dominate the result at long intervals."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NodeProfile:
    sleep_current_ma: float = 0.02  # 20 uA: ESP32 deep sleep + radio sleep + regulator
    active_current_ma: float = 40.0  # MCU awake, reading sensors, building the frame
    active_ms: float = 500.0
    tx_current_ma: float = 120.0  # SX1276 at +20 dBm is ~120 mA; ~45 mA at +14 dBm
    rx_current_ma: float = 11.0  # SX1276 receive
    rx_ms: float = 100.0  # RX1 + RX2 windows when nothing is received (class A)


@dataclass(frozen=True)
class BatteryResult:
    average_current_ma: float
    charge_per_cycle_mah: float
    tx_share: float  # fraction of the average current spent transmitting
    life_days: float
    life_years: float


def battery_life(
    capacity_mah: float,
    airtime_ms: float,
    messages_per_hour: float,
    profile: NodeProfile | None = None,
    usable_fraction: float = 0.8,
    self_discharge_per_year: float = 0.03,
) -> BatteryResult:
    if messages_per_hour <= 0:
        raise ValueError("messages_per_hour must be positive")
    profile = profile or NodeProfile()
    period_h = 1 / messages_per_hour
    tx_mah = profile.tx_current_ma * airtime_ms / 3.6e6
    rx_mah = profile.rx_current_ma * profile.rx_ms / 3.6e6
    active_mah = profile.active_current_ma * profile.active_ms / 3.6e6
    per_cycle = tx_mah + rx_mah + active_mah
    avg_ma = per_cycle / period_h + profile.sleep_current_ma
    usable = capacity_mah * usable_fraction
    # self discharge as an extra average current drawn from the nominal capacity
    self_ma = capacity_mah * self_discharge_per_year / (365 * 24)
    hours = usable / (avg_ma + self_ma)
    return BatteryResult(
        average_current_ma=avg_ma,
        charge_per_cycle_mah=per_cycle,
        tx_share=(tx_mah / period_h) / avg_ma,
        life_days=hours / 24,
        life_years=hours / 24 / 365,
    )
