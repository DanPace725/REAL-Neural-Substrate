from __future__ import annotations

from typing import Dict, Iterable, Tuple

from .types import DimensionScores


class TiltRegulatoryMesh:
    def __init__(
        self,
        coupling_pairs: Iterable[Tuple[str, str]] | None = None,
        viability_floor: float = 0.757,
        parametric_wall: float = 0.289,
        enabled: bool = True,
    ) -> None:
        self.coupling_pairs = tuple(
            coupling_pairs
            if coupling_pairs is not None
            else (
                ("continuity", "accountability"),
                ("vitality", "reflexivity"),
                ("contextual_fit", "differentiation"),
            )
        )
        self.viability_floor = viability_floor
        self.parametric_wall = parametric_wall
        self.enabled = enabled

    def apply(self, dimensions: DimensionScores) -> DimensionScores:
        if not self.enabled:
            return dict(dimensions)

        out: Dict[str, float] = dict(dimensions)

        for src, tgt in self.coupling_pairs:
            source = out.get(src, 0.0)
            target = out.get(tgt, 0.0)
            if source <= self.viability_floor:
                continue
            gap = source - target
            if gap <= 0:
                continue
            tilt = gap * self.parametric_wall
            out[tgt] = max(0.0, min(source, min(1.0, target + tilt)))

        return out
