"""Airtime checks against published LoRaWAN figures.

The reference values are the ones The Things Network documents for a 10-byte application
payload at 125 kHz (61.7 ms at SF7, 1482.8 ms at SF12); they follow from the SX1276 datasheet
formula with 13 bytes of LoRaWAN overhead, 8 preamble symbols, CR 4/5, explicit header, CRC."""

import math
from itertools import pairwise

import pytest

from lora_link_budget.airtime import airtime, bitrate_bps


@pytest.mark.parametrize(
    ("sf", "expected_ms"),
    [(7, 61.696), (8, 113.152), (9, 205.824), (10, 370.688), (11, 823.296), (12, 1482.752)],
)
def test_ttn_reference_10_bytes(sf, expected_ms):
    assert airtime(10, sf, 125_000).total_ms == pytest.approx(expected_ms, abs=1e-6)


def test_symbol_time_and_preamble_sf7():
    r = airtime(10, 7)
    assert r.symbol_time_ms == pytest.approx(1.024)
    assert r.preamble_ms == pytest.approx(12.25 * 1.024)
    assert r.payload_symbols == 48
    assert r.phy_payload_bytes == 23


def test_low_data_rate_optimisation_only_at_sf11_sf12_125k():
    assert [airtime(10, sf).low_data_rate_optimisation for sf in range(7, 13)] == [
        False,
        False,
        False,
        False,
        True,
        True,
    ]
    assert airtime(10, 11, 250_000).low_data_rate_optimisation is False


def test_raw_phy_payload_has_no_overhead():
    assert airtime(23, 7, lorawan=False).total_ms == airtime(10, 7).total_ms


def test_monotonic_in_sf_and_payload():
    times = [airtime(12, sf).total_ms for sf in range(7, 13)]
    assert times == sorted(times)
    sizes = [airtime(n, 9).total_ms for n in range(0, 60)]
    assert all(a <= b for a, b in pairwise(sizes))


def test_doubling_bandwidth_halves_airtime():
    assert airtime(20, 9, 250_000).total_ms == pytest.approx(airtime(20, 9, 125_000).total_ms / 2)


def test_bitrate_sf7_125k():
    assert bitrate_bps(7, 125_000) == pytest.approx(5468.75)


@pytest.mark.parametrize("kwargs", [{"sf": 13}, {"sf": 4}, {"bandwidth_hz": 100_000}])
def test_rejects_bad_parameters(kwargs):
    args = {"payload_bytes": 10, "sf": 7, "bandwidth_hz": 125_000}
    args.update(kwargs)
    with pytest.raises(ValueError):
        airtime(**args)


def test_us915_sf10_11_bytes_fits_dwell_time():
    assert airtime(11, 10).total_ms < 400
    assert math.isclose(airtime(11, 10).total_ms, 370.688, abs_tol=1e-6)
