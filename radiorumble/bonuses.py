"""Scoring modifiers — every one of them optional, and they stack.

A contact is worth a base number of points. Everything here adds to or scales
that, and each can be switched off independently, because the right mix
depends on what an organiser is trying to encourage. Rewarding QRP makes the
contest about skill rather than amplifiers; rewarding POTA and SOTA drags
people outdoors; rewarding DX turns it into a propagation game.

Nothing is on by default except the DX bonus. A modifier nobody asked for that
quietly changes a score is worse than no modifier at all.

Read from the log itself, so nothing has to be declared separately:

    TX_PWR              watts, for QRP
    SIG / SIG_INFO      POTA and SOTA references, e.g. "POTA K-1234"
    COMMENT             the same, for loggers that put it there instead
    MODE                FT4 as against FT8
    BAND                the US Technician HF allocations
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# The HF bands a US Technician licensee may use for digital modes, plus the
# VHF/UHF allocations they have in full. Working one means working somebody
# who may well be new to the hobby, which is worth encouraging.
TECHNICIAN_BANDS = frozenset({"10m", "6m", "2m", "1.25m", "70cm"})

_PARK = re.compile(r"\b(POTA|SOTA|WWFF|IOTA)\b", re.IGNORECASE)


@dataclass
class BonusRules:
    """Which modifiers are on, and what each is worth."""

    enabled: bool = True
    dx: int = 2
    qrp: int = 0
    qrp_watts: float = 20.0
    pota_sota: int = 0
    special_event: int = 0
    technician_band: int = 0
    ft4_multiplier: float = 1.0
    nil_penalty: int = 0
    special_calls: frozenset[str] = field(default_factory=frozenset)

    @classmethod
    def from_config(cls, data: dict | None) -> "BonusRules":
        data = data or {}
        return cls(
            enabled=bool(data.get("enabled", True)),
            dx=int(data.get("dx", 2)),
            qrp=int(data.get("qrp", 0)),
            qrp_watts=float(data.get("qrp_watts", 20)),
            pota_sota=int(data.get("pota_sota", 0)),
            special_event=int(data.get("special_event", 0)),
            technician_band=int(data.get("technician_band", 0)),
            ft4_multiplier=float(data.get("ft4_multiplier", 1.0)),
            nil_penalty=int(data.get("nil_penalty", 0)),
            special_calls=frozenset(
                c.upper() for c in data.get("special_calls", [])
            ),
        )

    @property
    def any_active(self) -> bool:
        return self.enabled and bool(
            self.dx or self.qrp or self.pota_sota or self.special_event
            or self.technician_band or self.ft4_multiplier != 1.0
        )

    # -- evaluation -------------------------------------------------------

    def evaluate(self, qso, base: int, is_dx: bool, skip=()) -> tuple[int, list[str]]:
        """What one contact is worth, and which modifiers applied.

        Returns whole points. The FT4 multiplier scales the total *after* the
        additions, so a bonus-laden FT4 contact is still worth half of the
        same contact on FT8 — which is the point of having it.
        """
        if not self.enabled:
            return base, []

        points = base
        applied: list[str] = []

        # DX mode already pays its own rate for a foreign contact, so it asks
        # for this to be skipped rather than being paid for the same thing twice.
        if self.dx and is_dx and "DX" not in skip:
            points += self.dx
            applied.append("DX")

        if self.qrp and self._is_qrp(qso):
            points += self.qrp
            applied.append("QRP")

        if self.pota_sota and self._is_portable_activation(qso):
            points += self.pota_sota
            applied.append("POTA/SOTA")

        if self.special_event and qso.call.upper() in self.special_calls:
            points += self.special_event
            applied.append("special event")

        if self.technician_band and qso.band.lower() in TECHNICIAN_BANDS:
            points += self.technician_band
            applied.append("technician band")

        if self.ft4_multiplier != 1.0 and qso.mode.upper() == "FT4":
            points = int(round(points * self.ft4_multiplier))
            applied.append("FT4")

        return max(0, points), applied

    # -- reading the log --------------------------------------------------

    def _is_qrp(self, qso) -> bool:
        """Whether the other station declared low power.

        Only counts when the log actually says so. Assuming QRP because a
        field is missing would hand the bonus to everyone.
        """
        raw = qso.raw.get("tx_pwr") or qso.raw.get("rx_pwr") or ""
        try:
            return self.qrp_limit_ok(float(str(raw).lower().replace("w", "").strip()))
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _is_portable_activation(qso) -> bool:
        for key in ("sig", "sig_info", "comment", "my_sig", "my_sig_info", "notes"):
            if _PARK.search(str(qso.raw.get(key, ""))):
                return True
        return False

    def qrp_limit_ok(self, watts: float) -> bool:
        return 0 < watts <= self.qrp_watts
