"""Receiver sensitivity, link budget and maximum range."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .pathloss import PathLossModel

# Minimum demodulation SNR per spreading factor, SX1276 datasheet table "LoRa modem SNR".
SNR_LIMIT_DB = {5: -2.5, 6: -5.0, 7: -7.5, 8: -10.0, 9: -12.5, 10: -15.0, 11: -17.5, 12: -20.0}
THERMAL_NOISE_DBM_HZ = -174.0


def sensitivity_dbm(sf: int, bandwidth_hz: int = 125_000, noise_figure_db: float = 6.0) -> float:
    """S = -174 dBm/Hz + 10 log10(BW) + NF + SNR_limit(SF).

    With NF = 6 dB this lands within about 1-2 dB of the typical values printed in the SX1276
    datasheet (for example -137 dBm at SF12 / 125 kHz, -124.5 here against -123 for SF7)."""
    if sf not in SNR_LIMIT_DB:
        raise ValueError(f"spreading factor must be 5..12, got {sf}")
    return THERMAL_NOISE_DBM_HZ + 10 * math.log10(bandwidth_hz) + noise_figure_db + SNR_LIMIT_DB[sf]


@dataclass(frozen=True)
class LinkBudget:
    """Everything on the RF path except the propagation loss. Powers in dBm, gains/losses in dB."""

    tx_power_dbm: float = 14.0
    tx_antenna_gain_dbi: float = 2.0
    tx_cable_loss_db: float = 0.5
    rx_antenna_gain_dbi: float = 2.0
    rx_cable_loss_db: float = 0.5
    fade_margin_db: float = 10.0
    noise_figure_db: float = 6.0
    extra_loss_db: float = 0.0  # vegetation, walls, body loss; added on top of the model

    @property
    def eirp_dbm(self) -> float:
        return self.tx_power_dbm + self.tx_antenna_gain_dbi - self.tx_cable_loss_db

    def max_path_loss_db(self, sf: int, bandwidth_hz: int = 125_000) -> float:
        """Largest propagation loss the link tolerates while keeping the fade margin."""
        return (
            self.eirp_dbm
            + self.rx_antenna_gain_dbi
            - self.rx_cable_loss_db
            - self.extra_loss_db
            - self.fade_margin_db
            - sensitivity_dbm(sf, bandwidth_hz, self.noise_figure_db)
        )

    def evaluate(
        self, model: PathLossModel, distance_m: float, sf: int, bandwidth_hz: int = 125_000
    ) -> LinkResult:
        loss = model.loss_db(distance_m) + self.extra_loss_db
        sens = sensitivity_dbm(sf, bandwidth_hz, self.noise_figure_db)
        rx = self.eirp_dbm + self.rx_antenna_gain_dbi - self.rx_cable_loss_db - loss
        return LinkResult(
            model=model.name,
            distance_m=distance_m,
            sf=sf,
            bandwidth_hz=bandwidth_hz,
            path_loss_db=loss,
            sensitivity_dbm=sens,
            rx_power_dbm=rx,
            margin_db=rx - sens,
            required_fade_margin_db=self.fade_margin_db,
            max_range_m=model.distance_m(self.max_path_loss_db(sf, bandwidth_hz)),
            warnings=model.warnings(distance_m),
        )


@dataclass(frozen=True)
class LinkResult:
    model: str
    distance_m: float
    sf: int
    bandwidth_hz: int
    path_loss_db: float
    sensitivity_dbm: float
    rx_power_dbm: float
    margin_db: float  # rx power above sensitivity, before any fade margin
    required_fade_margin_db: float
    max_range_m: float  # distance at which margin_db == required_fade_margin_db
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.margin_db >= self.required_fade_margin_db
