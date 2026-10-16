"""Regional rules that matter for a sensor node: EU868 duty cycle, US915 dwell time, maximum
EIRP and maximum application payload per data rate (LoRaWAN Regional Parameters RP002)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Region:
    name: str
    frequency_mhz: float
    bandwidth_hz: int
    uplink_sfs: tuple[int, ...]
    max_eirp_dbm: float
    duty_cycle: float | None  # fraction of time a device may transmit in the sub-band
    max_dwell_ms: float | None  # longest single transmission allowed
    max_app_payload: dict[int, int]  # SF -> application payload bytes (N, no FOpts)
    note: str


REGIONS: dict[str, Region] = {
    "EU868": Region(
        name="EU868",
        frequency_mhz=868.0,
        bandwidth_hz=125_000,
        uplink_sfs=(7, 8, 9, 10, 11, 12),
        max_eirp_dbm=16.0,  # 14 dBm ERP
        duty_cycle=0.01,  # 1 % in the 868.0-868.6 MHz sub-band used by the default channels
        max_dwell_ms=None,
        max_app_payload={12: 51, 11: 51, 10: 51, 9: 115, 8: 222, 7: 222},
        note="ETSI EN 300 220: 1 % duty cycle per sub-band (g1). TTN additionally asks for "
        "30 s uplink airtime per device per day (fair-use policy, not law).",
    ),
    "US915": Region(
        name="US915",
        frequency_mhz=915.0,
        bandwidth_hz=125_000,
        uplink_sfs=(7, 8, 9, 10),
        max_eirp_dbm=30.0,
        duty_cycle=None,
        max_dwell_ms=400.0,
        max_app_payload={10: 11, 9: 53, 8: 125, 7: 242},
        note="FCC Part 15.247: no duty cycle, but 400 ms maximum dwell time per channel, which "
        "is why SF11/SF12 uplinks are not allowed at 125 kHz.",
    ),
}

TTN_FAIR_USE_S_PER_DAY = 30.0


@dataclass(frozen=True)
class DutyCycleResult:
    region: str
    airtime_ms: float
    messages_per_hour: float
    utilisation: float  # fraction of time transmitting
    limit: float | None
    max_messages_per_hour: float | None
    dwell_ok: bool
    airtime_per_day_s: float
    ttn_fair_use_ok: bool
    problems: list[str]

    @property
    def ok(self) -> bool:
        return not self.problems


def duty_cycle_check(
    region: Region, airtime_ms: float, messages_per_hour: float, sf: int, app_payload_bytes: int
) -> DutyCycleResult:
    utilisation = airtime_ms / 1000 * messages_per_hour / 3600
    problems: list[str] = []
    max_msgs = None
    if region.duty_cycle is not None:
        max_msgs = region.duty_cycle * 3600 / (airtime_ms / 1000)
        if utilisation > region.duty_cycle:
            problems.append(
                f"duty cycle {utilisation:.2%} exceeds {region.duty_cycle:.1%} "
                f"(max {max_msgs:.0f} messages/hour at this airtime)"
            )
    dwell_ok = region.max_dwell_ms is None or airtime_ms <= region.max_dwell_ms
    if not dwell_ok:
        problems.append(f"airtime {airtime_ms:.0f} ms exceeds {region.max_dwell_ms:.0f} ms dwell")
    if sf not in region.uplink_sfs:
        problems.append(f"SF{sf} is not an uplink data rate in {region.name}")
    elif app_payload_bytes > region.max_app_payload[sf]:
        problems.append(
            f"{app_payload_bytes} bytes exceeds the {region.max_app_payload[sf]}-byte "
            f"maximum payload at SF{sf}"
        )
    per_day = airtime_ms / 1000 * messages_per_hour * 24
    return DutyCycleResult(
        region=region.name,
        airtime_ms=airtime_ms,
        messages_per_hour=messages_per_hour,
        utilisation=utilisation,
        limit=region.duty_cycle,
        max_messages_per_hour=max_msgs,
        dwell_ok=dwell_ok,
        airtime_per_day_s=per_day,
        ttn_fair_use_ok=per_day <= TTN_FAIR_USE_S_PER_DAY,
        problems=problems,
    )
