"""LoRa time-on-air, from the formula in the Semtech SX1276 datasheet (section 4.1.1.6).

T_sym      = 2**SF / BW
T_preamble = (n_preamble + 4.25) * T_sym
n_payload  = 8 + max(ceil((8*PL - 4*SF + 28 + 16*CRC - 20*IH) / (4*(SF - 2*DE))) * (CR + 4), 0)
T_packet   = T_preamble + n_payload * T_sym

PL is the PHY payload in bytes. A LoRaWAN uplink adds 13 bytes of MAC header, device address,
frame control, counter, port and MIC around the application payload, so PL = app_bytes + 13.
DE (low data-rate optimisation) is switched on when T_sym exceeds 16 ms, which at 125 kHz means
SF11 and SF12. The LoRaWAN defaults are 8 preamble symbols, CR 4/5, explicit header, CRC on.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

LORAWAN_OVERHEAD_BYTES = 13
LDRO_SYMBOL_TIME_S = 0.016


@dataclass(frozen=True)
class AirtimeResult:
    sf: int
    bandwidth_hz: int
    phy_payload_bytes: int
    symbol_time_ms: float
    preamble_ms: float
    payload_symbols: int
    low_data_rate_optimisation: bool
    total_ms: float


def airtime(
    payload_bytes: int,
    sf: int,
    bandwidth_hz: int = 125_000,
    *,
    lorawan: bool = True,
    preamble_symbols: int = 8,
    coding_rate: int = 1,
    explicit_header: bool = True,
    crc: bool = True,
) -> AirtimeResult:
    """Time on air of one LoRa frame. `payload_bytes` is the application payload when
    `lorawan` is True (13 bytes of LoRaWAN overhead are added), else the raw PHY payload."""
    if not 5 <= sf <= 12:
        raise ValueError(f"spreading factor must be 5..12, got {sf}")
    if bandwidth_hz not in (
        7_800,
        10_400,
        15_600,
        20_800,
        31_250,
        41_700,
        62_500,
        125_000,
        250_000,
        500_000,
    ):
        raise ValueError(f"unsupported bandwidth {bandwidth_hz} Hz")
    if not 1 <= coding_rate <= 4:
        raise ValueError("coding_rate is the CR denominator offset: 1 (4/5) .. 4 (4/8)")
    if payload_bytes < 0:
        raise ValueError("payload must be non-negative")

    pl = payload_bytes + (LORAWAN_OVERHEAD_BYTES if lorawan else 0)
    t_sym = 2**sf / bandwidth_hz
    de = 1 if t_sym > LDRO_SYMBOL_TIME_S else 0
    ih = 0 if explicit_header else 1
    numerator = 8 * pl - 4 * sf + 28 + 16 * int(crc) - 20 * ih
    denominator = 4 * (sf - 2 * de)
    n_payload = 8 + max(math.ceil(numerator / denominator) * (coding_rate + 4), 0)
    t_preamble = (preamble_symbols + 4.25) * t_sym
    total = t_preamble + n_payload * t_sym
    return AirtimeResult(
        sf=sf,
        bandwidth_hz=bandwidth_hz,
        phy_payload_bytes=pl,
        symbol_time_ms=t_sym * 1e3,
        preamble_ms=t_preamble * 1e3,
        payload_symbols=n_payload,
        low_data_rate_optimisation=bool(de),
        total_ms=total * 1e3,
    )


def bitrate_bps(sf: int, bandwidth_hz: int = 125_000, coding_rate: int = 1) -> float:
    """Nominal LoRa bit rate: SF * BW / 2**SF * 4 / (4 + CR)."""
    return sf * bandwidth_hz / 2**sf * 4 / (4 + coding_rate)
