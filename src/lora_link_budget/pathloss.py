"""Path-loss models and their inverses (path loss -> distance).

All distances in metres, frequencies in MHz, losses in dB.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Protocol


class PathLossModel(Protocol):
    name: str

    def loss_db(self, distance_m: float) -> float: ...

    def distance_m(self, loss_db: float) -> float: ...

    def warnings(self, distance_m: float) -> list[str]: ...


def fspl_db(distance_m: float, frequency_mhz: float) -> float:
    """Free-space path loss: 20 log10(d_km) + 20 log10(f_MHz) + 32.44."""
    if distance_m <= 0:
        raise ValueError("distance must be positive")
    return 20 * math.log10(distance_m / 1000) + 20 * math.log10(frequency_mhz) + 32.44


@dataclass(frozen=True)
class free_space:  # noqa: N801 - used like a constructor: free_space(868)
    frequency_mhz: float
    name: str = "free space"

    def loss_db(self, distance_m: float) -> float:
        return fspl_db(distance_m, self.frequency_mhz)

    def distance_m(self, loss_db: float) -> float:
        return 1000 * 10 ** ((loss_db - 32.44 - 20 * math.log10(self.frequency_mhz)) / 20)

    def warnings(self, distance_m: float) -> list[str]:
        return ["free space is a best case: no ground, vegetation or buildings"]


@dataclass(frozen=True)
class log_distance:  # noqa: N801
    """PL(d) = FSPL(d0) + 10 n log10(d / d0). n = 2 is free space; 2.7-3.5 is typical for
    suburban / light vegetation; 3.5-4.5 for obstructed paths. d0 is 1 m by default."""

    frequency_mhz: float
    exponent: float = 3.0
    reference_m: float = 1.0
    name: str = "log-distance"

    def loss_db(self, distance_m: float) -> float:
        if distance_m <= 0:
            raise ValueError("distance must be positive")
        return fspl_db(self.reference_m, self.frequency_mhz) + 10 * self.exponent * math.log10(
            distance_m / self.reference_m
        )

    def distance_m(self, loss_db: float) -> float:
        pl0 = fspl_db(self.reference_m, self.frequency_mhz)
        return self.reference_m * 10 ** ((loss_db - pl0) / (10 * self.exponent))

    def warnings(self, distance_m: float) -> list[str]:
        return [
            f"log-distance with n={self.exponent:g}: the exponent is a site assumption, "
            "not a measurement"
        ]


@dataclass(frozen=True)
class Hata:
    """Okumura-Hata (Hata 1980). Valid for 150-1500 MHz, base antenna 30-200 m, mobile antenna
    1-10 m, 1-20 km. Environments: 'urban' (small/medium city), 'suburban', 'open' (rural).
    Below the valid ranges the closed form still returns a number; `warnings()` says so."""

    frequency_mhz: float
    base_height_m: float
    mobile_height_m: float = 1.5
    environment: str = "open"

    @property
    def name(self) -> str:
        return f"Okumura-Hata ({self.environment})"

    def _a_hm(self) -> float:
        f, hm = self.frequency_mhz, self.mobile_height_m
        return (1.1 * math.log10(f) - 0.7) * hm - (1.56 * math.log10(f) - 0.8)

    def _coefficients(self) -> tuple[float, float]:
        """Return (A, B) such that loss = A + B log10(d_km)."""
        f, hb = self.frequency_mhz, self.base_height_m
        a = 69.55 + 26.16 * math.log10(f) - 13.82 * math.log10(hb) - self._a_hm()
        b = 44.9 - 6.55 * math.log10(hb)
        if self.environment == "suburban":
            a -= 2 * math.log10(f / 28) ** 2 + 5.4
        elif self.environment == "open":
            a -= 4.78 * math.log10(f) ** 2 - 18.33 * math.log10(f) + 40.94
        elif self.environment != "urban":
            raise ValueError("environment must be urban, suburban or open")
        return a, b

    def loss_db(self, distance_m: float) -> float:
        if distance_m <= 0:
            raise ValueError("distance must be positive")
        a, b = self._coefficients()
        return a + b * math.log10(distance_m / 1000)

    def distance_m(self, loss_db: float) -> float:
        a, b = self._coefficients()
        return 1000 * 10 ** ((loss_db - a) / b)

    def warnings(self, distance_m: float) -> list[str]:
        out = []
        if not 150 <= self.frequency_mhz <= 1500:
            out.append("Hata: frequency outside 150-1500 MHz")
        if not 30 <= self.base_height_m <= 200:
            out.append(
                f"Hata: gateway height {self.base_height_m:g} m outside 30-200 m "
                "(model extrapolated; real loss is usually higher for low masts)"
            )
        if not 1 <= self.mobile_height_m <= 10:
            out.append("Hata: node height outside 1-10 m")
        if not 1000 <= distance_m <= 20_000:
            out.append("Hata: distance outside 1-20 km (extrapolated)")
        return out
