import math

import pytest

from lora_link_budget import Hata, LinkBudget, free_space, log_distance, sensitivity_dbm
from lora_link_budget.pathloss import fspl_db


def test_free_space_textbook_value_868mhz_1km():
    assert fspl_db(1000, 868) == pytest.approx(91.22, abs=0.01)


def test_free_space_6db_per_doubling():
    assert fspl_db(2000, 868) - fspl_db(1000, 868) == pytest.approx(20 * math.log10(2))


def test_log_distance_n2_equals_free_space():
    for d in (10, 500, 3000):
        assert log_distance(868, 2.0).loss_db(d) == pytest.approx(fspl_db(d, 868))


def test_hata_urban_900mhz_1km_classic_value():
    # 900 MHz, hb 30 m, hm 1.5 m, 1 km: A = 126.4 dB when the Hata equations are worked by hand.
    assert Hata(900, 30, 1.5, "urban").loss_db(1000) == pytest.approx(126.4, abs=0.1)


def test_hata_environment_ordering():
    urban, sub, open_ = (Hata(868, 30, 1.5, e).loss_db(5000) for e in ("urban", "suburban", "open"))
    assert urban > sub > open_


def test_hata_warnings_for_low_mast():
    assert any("30-200" in w for w in Hata(868, 10).warnings(2000))
    assert any("1-20 km" in w for w in Hata(868, 30).warnings(500))
    assert Hata(868, 30).warnings(2000) == []


@pytest.mark.parametrize(
    "model", [free_space(868), log_distance(868, 3.2), Hata(915, 40, 2, "suburban")]
)
def test_distance_inverts_loss(model):
    for d in (200, 1500, 9000):
        assert model.distance_m(model.loss_db(d)) == pytest.approx(d, rel=1e-9)


def test_sensitivity_matches_datasheet_order_of_magnitude():
    assert sensitivity_dbm(12, 125_000) == pytest.approx(-137.0, abs=0.05)
    assert sensitivity_dbm(7, 125_000) == pytest.approx(-124.5, abs=0.05)
    assert sensitivity_dbm(7, 250_000) == pytest.approx(-124.5 + 10 * math.log10(2), abs=0.05)


def test_eirp_and_margin_arithmetic():
    b = LinkBudget(14, 2, 0.5, 2, 0.5, fade_margin_db=10, noise_figure_db=6)
    assert b.eirp_dbm == pytest.approx(15.5)
    r = b.evaluate(free_space(868), 1000, 7)
    assert r.rx_power_dbm == pytest.approx(15.5 + 1.5 - 91.22, abs=0.01)
    assert r.margin_db == pytest.approx(r.rx_power_dbm - r.sensitivity_dbm)
    assert r.sensitivity_dbm == pytest.approx(-124.5, abs=0.05)
    assert r.ok


def test_max_range_is_where_margin_equals_fade_margin():
    b = LinkBudget(fade_margin_db=10)
    model = log_distance(868, 3.0)
    r = b.evaluate(model, 1000, 9)
    at_edge = b.evaluate(model, r.max_range_m, 9)
    assert at_edge.margin_db == pytest.approx(10.0, abs=1e-6)
    assert not b.evaluate(model, r.max_range_m * 1.01, 9).ok


def test_extra_loss_reduces_range():
    plain = LinkBudget().max_path_loss_db(7)
    assert LinkBudget(extra_loss_db=6).max_path_loss_db(7) == pytest.approx(plain - 6)
