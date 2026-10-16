import pytest

from lora_link_budget import REGIONS, airtime, battery_life, duty_cycle_check
from lora_link_budget.battery import NodeProfile


def test_eu868_one_percent_limit_counts_messages():
    eu = REGIONS["EU868"]
    t = airtime(10, 7).total_ms  # 61.696 ms
    r = duty_cycle_check(eu, t, 6, 7, 10)
    assert r.utilisation == pytest.approx(6 * 0.061696 / 3600)
    assert r.max_messages_per_hour == pytest.approx(36 / 0.061696)  # 583.5
    assert r.ok and r.ttn_fair_use_ok
    assert not duty_cycle_check(eu, t, 600, 7, 10).ok  # 600/h > 583/h


def test_eu868_sf12_every_minute_breaks_duty_cycle_and_fair_use():
    eu = REGIONS["EU868"]
    r = duty_cycle_check(eu, airtime(10, 12).total_ms, 60, 12, 10)
    assert r.utilisation == pytest.approx(60 * 1.482752 / 3600)
    assert r.utilisation > 0.01 and not r.ok  # 60 * 1.48 s / 3600 s = 2.5 %
    assert not r.ttn_fair_use_ok


def test_us915_dwell_time_rejects_sf11_and_long_frames():
    us = REGIONS["US915"]
    bad = duty_cycle_check(us, airtime(10, 11).total_ms, 6, 11, 10)
    assert not bad.dwell_ok and not bad.ok
    assert any("not an uplink" in p for p in bad.problems)
    good = duty_cycle_check(us, airtime(11, 10).total_ms, 6, 10, 11)
    assert good.ok and good.max_messages_per_hour is None


def test_max_payload_per_data_rate():
    eu = REGIONS["EU868"]
    assert not duty_cycle_check(eu, airtime(52, 12).total_ms, 1, 12, 52).ok
    assert duty_cycle_check(eu, airtime(51, 12).total_ms, 1, 12, 51).ok
    us = REGIONS["US915"]
    assert not duty_cycle_check(us, airtime(12, 10).total_ms, 1, 10, 12).ok


def test_battery_sleep_only_bound():
    # One message per hour with zero active/TX/RX cost: life = usable capacity / sleep current.
    p = NodeProfile(
        sleep_current_ma=0.02,
        active_current_ma=0,
        active_ms=0,
        tx_current_ma=0,
        rx_current_ma=0,
        rx_ms=0,
    )
    r = battery_life(2000, 100, 1, p, usable_fraction=1.0, self_discharge_per_year=0.0)
    assert r.average_current_ma == pytest.approx(0.02)
    assert r.life_days == pytest.approx(2000 / 0.02 / 24)


def test_battery_tx_charge_arithmetic():
    p = NodeProfile(
        sleep_current_ma=0,
        active_current_ma=0,
        active_ms=0,
        tx_current_ma=120,
        rx_current_ma=0,
        rx_ms=0,
    )
    r = battery_life(1000, 1000, 60, p, usable_fraction=1.0, self_discharge_per_year=0.0)
    # 120 mA for 1 s, 60 times an hour = 7200 mA*s/h = 2 mAh/h
    assert r.average_current_ma == pytest.approx(2.0)
    assert r.tx_share == pytest.approx(1.0)
    assert r.life_days == pytest.approx(1000 / 2.0 / 24)


def test_longer_interval_longer_life():
    t = airtime(12, 9).total_ms
    assert battery_life(2400, t, 1).life_days > battery_life(2400, t, 6).life_days


def test_battery_rejects_zero_rate():
    with pytest.raises(ValueError):
        battery_life(2400, 100, 0)
