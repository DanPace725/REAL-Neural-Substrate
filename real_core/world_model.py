from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Any, Dict, List

from .substrate import MemorySubstrate, SubstrateConfig
from .types import SliceSummary, SubstrateSnapshot

WORLD_MODEL_HYPOTHESES: tuple[str, ...] = ("h0", "h1", "h2", "h3", "unknown")
WORLD_MODEL_ASSISTANCE_MODES: tuple[str, ...] = ("off", "hinted", "guided", "teacher")
_KNOWN_HYPOTHESES = WORLD_MODEL_HYPOTHESES[:-1]
_HYPOTHESIS_INDEX = {name: index for index, name in enumerate(_KNOWN_HYPOTHESES)}


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _round4(value: float) -> float:
    return round(float(value), 4)


def _final_accuracy(summary: SliceSummary) -> float:
    return float(
        summary.metadata.get(
            "final_accuracy",
            summary.metadata.get("mean_bit_accuracy", 0.0),
        )
    )


def _floor_accuracy(summary: SliceSummary) -> float:
    if summary.context_accuracy:
        return min(float(value) for value in summary.context_accuracy.values())
    return float(
        summary.metadata.get(
            "worst_context_accuracy",
            summary.metadata.get("floor_accuracy", _final_accuracy(summary)),
        )
    )


def _context_spread(summary: SliceSummary) -> float:
    if summary.context_accuracy:
        values = [float(value) for value in summary.context_accuracy.values()]
    else:
        values = [_final_accuracy(summary)]
    return max(0.0, max(values) - min(values))


def _context_debt_summary(
    history: List[SliceSummary],
    *,
    accuracy_threshold: float,
) -> dict[str, float]:
    if not history or accuracy_threshold <= 0.0:
        return {
            "max_context_debt": 0.0,
            "total_context_debt": 0.0,
            "open_context_count": 0.0,
        }
    context_keys: list[str] = []
    for summary in history:
        for key in summary.context_accuracy:
            if key not in context_keys:
                context_keys.append(str(key))
    if not context_keys:
        context_keys = ["aggregate"]
    debt: dict[str, float] = {key: 0.0 for key in context_keys}
    for summary in history:
        observed = dict(summary.context_accuracy)
        for key in context_keys:
            if observed:
                if key not in observed:
                    debt[key] *= 0.85
                    continue
                accuracy = float(observed[key])
            else:
                if key != "aggregate":
                    debt[key] *= 0.85
                    continue
                accuracy = _final_accuracy(summary)
            shortfall = max(0.0, accuracy_threshold - accuracy)
            surplus = max(0.0, accuracy - accuracy_threshold)
            debt[key] = min(3.0, debt[key] * 0.85 + shortfall)
            if surplus > 0.0:
                debt[key] = max(0.0, debt[key] - 0.75 * surplus)
    return {
        "max_context_debt": max(float(value) for value in debt.values()),
        "total_context_debt": sum(float(value) for value in debt.values()),
        "open_context_count": float(sum(1 for value in debt.values() if value > 0.05)),
    }


def _estimate_hypothesis(raw_value: Any) -> str | None:
    try:
        value = int(float(raw_value))
    except (TypeError, ValueError):
        return None
    return f"h{value}" if 0 <= value <= 3 else None


def _history_enabled(history: List[SliceSummary]) -> bool:
    if not history:
        return False
    current = history[-1]
    return bool(
        str(current.benchmark_family).upper().startswith("C")
        or bool(current.metadata.get("world_model_opt_in"))
    )


@dataclass
class WorldModelCycleResult:
    summary: dict[str, Any]
    updated: bool
    update_reason: str
    action: str


@dataclass
class WorldModelAssistance:
    mode: str = "off"
    active: bool = False
    target: str | None = None
    alternative: str | None = None
    confidence: float = 0.0
    source: str = "none"
    note: str = ""


class WorldModelObservationAdapter:
    def __init__(self, *, accuracy_threshold: float = 0.75) -> None:
        self.accuracy_threshold = float(accuracy_threshold)

    def observe(self, history: List[SliceSummary]) -> Dict[str, float]:
        if not history:
            return {
                "slice_ambiguity": 0.0,
                "transform_commitment_margin": 0.0,
                "context_spread": 0.0,
                "floor_accuracy": 0.0,
                "context_debt": 0.0,
                "open_context_count": 0.0,
                "forecast_regime_accuracy": 0.0,
                "source_sequence_confidence": 0.0,
                "source_route_confidence": 0.0,
                "source_feedback_confidence": 0.0,
                "source_sequence_estimate": -1.0,
                "source_route_estimate": -1.0,
                "source_feedback_estimate": -1.0,
                "revisit_marker": 0.0,
                "dead_end_marker": 0.0,
                "progress_velocity": 0.0,
            }
        current = history[-1]
        previous = history[-2] if len(history) >= 2 else None
        forecast_metrics = dict(current.metadata.get("forecast_metrics", {}))
        regime_accuracy = {
            str(key): float(value)
            for key, value in dict(forecast_metrics.get("forecast_regime_accuracy", {})).items()
        }
        debt_summary = _context_debt_summary(
            history,
            accuracy_threshold=self.accuracy_threshold,
        )
        floor_accuracy = _floor_accuracy(current)
        previous_floor = floor_accuracy if previous is None else _floor_accuracy(previous)
        return {
            "slice_ambiguity": _clamp01(
                float(
                    current.metadata.get(
                        "mean_provisional_context_ambiguity",
                        current.ambiguity_level,
                    )
                )
            ),
            "transform_commitment_margin": _clamp01(
                float(current.metadata.get("mean_transform_commitment_margin", 0.0))
            ),
            "context_spread": _clamp01(_context_spread(current)),
            "floor_accuracy": _clamp01(floor_accuracy),
            "context_debt": _clamp01(float(debt_summary.get("max_context_debt", 0.0)) / 3.0),
            "open_context_count": _clamp01(
                float(debt_summary.get("open_context_count", 0.0)) / 4.0
            ),
            "forecast_regime_accuracy": _clamp01(
                mean(regime_accuracy.values()) if regime_accuracy else 0.0
            ),
            "source_sequence_confidence": _clamp01(
                float(
                    current.metadata.get(
                        "source_sequence_channel_context_confidence",
                        current.metadata.get("source_sequence_context_confidence", 0.0),
                    )
                )
            ),
            "source_route_confidence": _clamp01(
                float(current.metadata.get("source_route_context_confidence", 0.0))
            ),
            "source_feedback_confidence": _clamp01(
                float(current.metadata.get("source_feedback_context_confidence", 0.0))
            ),
            "source_sequence_estimate": float(
                current.metadata.get("source_sequence_context_estimate", -1.0)
            ),
            "source_route_estimate": float(
                current.metadata.get("source_route_context_estimate", -1.0)
            ),
            "source_feedback_estimate": float(
                current.metadata.get("source_feedback_context_estimate", -1.0)
            ),
            "revisit_marker": _clamp01(
                float(current.metadata.get("world_model_revisit_marker", 0.0))
            ),
            "dead_end_marker": _clamp01(
                float(current.metadata.get("world_model_dead_end_marker", 0.0))
            ),
            "progress_velocity": _clamp01(0.5 + 3.0 * (floor_accuracy - previous_floor)),
        }


class REALWorldModel:
    def __init__(
        self,
        *,
        update_stride: int = 3,
        ambiguity_threshold: float = 0.55,
        ambiguity_streak: int = 2,
        accuracy_threshold: float = 0.75,
        assistance_mode: str = "off",
        assistance_confidence_threshold: float = 0.45,
    ) -> None:
        self.update_stride = max(1, int(update_stride))
        self.ambiguity_threshold = float(ambiguity_threshold)
        self.ambiguity_streak = max(1, int(ambiguity_streak))
        self.accuracy_threshold = float(accuracy_threshold)
        self.assistance_mode = (
            str(assistance_mode).lower()
            if str(assistance_mode).lower() in WORLD_MODEL_ASSISTANCE_MODES
            else "off"
        )
        self.assistance_confidence_threshold = _clamp01(assistance_confidence_threshold)
        self.adapter = WorldModelObservationAdapter(accuracy_threshold=accuracy_threshold)
        self.substrate = MemorySubstrate(
            SubstrateConfig(
                keys=WORLD_MODEL_HYPOTHESES,
                slow_decay=0.015,
                bistable_threshold=0.18,
                write_base_cost=0.08,
                maintain_base_cost=0.02,
            )
        )
        self.contradiction: Dict[str, float] = {key: 0.0 for key in WORLD_MODEL_HYPOTHESES}
        self.revisit_credit: Dict[str, float] = {key: 0.0 for key in WORLD_MODEL_HYPOTHESES}
        self.dead_end_penalty: Dict[str, float] = {key: 0.0 for key in WORLD_MODEL_HYPOTHESES}
        self.transition_affinity: Dict[str, Dict[str, float]] = {
            key: {inner: 0.0 for inner in WORLD_MODEL_HYPOTHESES}
            for key in WORLD_MODEL_HYPOTHESES
        }
        self.last_action = "hold_open"
        self.last_update_reason = "init"
        self.last_update_slice_id = 0
        self.last_summary: dict[str, Any] = {}
        self.last_top_hypothesis = "unknown"
        self.high_ambiguity_streak = 0
        self.revisit_hit_count = 0
        self.dead_end_hit_count = 0
        self.archived_paths: list[dict[str, Any]] = []
        self.last_assistance = WorldModelAssistance(mode=self.assistance_mode)

    def enabled_for(self, history: List[SliceSummary]) -> bool:
        return _history_enabled(history)

    def process(self, history: List[SliceSummary]) -> WorldModelCycleResult | None:
        if not history:
            return None
        if not self.enabled_for(history):
            self.last_summary = {}
            return None
        current = history[-1]
        observation = self.adapter.observe(history)
        if observation["slice_ambiguity"] >= self.ambiguity_threshold:
            self.high_ambiguity_streak += 1
        else:
            self.high_ambiguity_streak = 0
        evidence = self._build_hypothesis_evidence(observation)
        assistance = self._resolve_assistance(history, observation, evidence)
        evidence = self._apply_assistance_to_evidence(evidence, assistance)
        triggers = self._detect_triggers(history, observation, evidence, assistance)
        should_update, update_reason = self._should_update(current.slice_id, triggers)
        action = self.last_action
        if should_update:
            action = self._select_action(observation, evidence, triggers, assistance)
            self._apply_action(
                action,
                evidence,
                observation,
                triggers,
                current.slice_id,
                assistance,
            )
        summary = self.summary()
        summary["assistance"] = {
            "mode": assistance.mode,
            "active": bool(assistance.active),
            "target": assistance.target,
            "alternative": assistance.alternative,
            "confidence": _round4(assistance.confidence),
            "source": assistance.source,
            "note": assistance.note,
        }
        summary["updated_this_slice"] = bool(should_update)
        summary["update_reason"] = update_reason
        summary["slice_id"] = int(current.slice_id)
        self.last_summary = dict(summary)
        self.last_assistance = assistance
        return WorldModelCycleResult(
            summary=summary,
            updated=bool(should_update),
            update_reason=update_reason,
            action=action,
        )

    def export_state(self) -> dict[str, Any]:
        return {
            "substrate": self.substrate.save_state(),
            "contradiction": dict(self.contradiction),
            "revisit_credit": dict(self.revisit_credit),
            "dead_end_penalty": dict(self.dead_end_penalty),
            "transition_affinity": {
                key: dict(values) for key, values in self.transition_affinity.items()
            },
            "last_action": self.last_action,
            "last_update_reason": self.last_update_reason,
            "last_update_slice_id": self.last_update_slice_id,
            "last_top_hypothesis": self.last_top_hypothesis,
            "high_ambiguity_streak": self.high_ambiguity_streak,
            "revisit_hit_count": self.revisit_hit_count,
            "dead_end_hit_count": self.dead_end_hit_count,
            "archived_paths": list(self.archived_paths),
            "last_summary": dict(self.last_summary),
            "last_assistance": {
                "mode": self.last_assistance.mode,
                "active": self.last_assistance.active,
                "target": self.last_assistance.target,
                "alternative": self.last_assistance.alternative,
                "confidence": self.last_assistance.confidence,
                "source": self.last_assistance.source,
                "note": self.last_assistance.note,
            },
            "config": {
                "update_stride": self.update_stride,
                "ambiguity_threshold": self.ambiguity_threshold,
                "ambiguity_streak": self.ambiguity_streak,
                "accuracy_threshold": self.accuracy_threshold,
                "assistance_mode": self.assistance_mode,
                "assistance_confidence_threshold": self.assistance_confidence_threshold,
            },
        }

    def load_state(self, payload: dict[str, Any] | None) -> None:
        if not payload:
            return
        substrate_payload = payload.get("substrate")
        if isinstance(substrate_payload, SubstrateSnapshot):
            self.substrate.load_state(substrate_payload)
        elif isinstance(substrate_payload, dict):
            self.substrate.load_state(
                SubstrateSnapshot(
                    fast=dict(substrate_payload.get("fast", {})),
                    slow=dict(substrate_payload.get("slow", {})),
                    slow_age=dict(substrate_payload.get("slow_age", {})),
                    slow_velocity=dict(substrate_payload.get("slow_velocity", {})),
                    metadata=dict(substrate_payload.get("metadata", {})),
                )
            )
        for name, target in (
            ("contradiction", self.contradiction),
            ("revisit_credit", self.revisit_credit),
            ("dead_end_penalty", self.dead_end_penalty),
        ):
            source = dict(payload.get(name, {}))
            for key in WORLD_MODEL_HYPOTHESES:
                target[key] = _clamp01(float(source.get(key, 0.0)))
        transition_payload = dict(payload.get("transition_affinity", {}))
        self.transition_affinity = {
            key: {
                inner: _clamp01(float(dict(transition_payload.get(key, {})).get(inner, 0.0)))
                for inner in WORLD_MODEL_HYPOTHESES
            }
            for key in WORLD_MODEL_HYPOTHESES
        }
        self.last_action = str(payload.get("last_action", self.last_action))
        self.last_update_reason = str(
            payload.get("last_update_reason", self.last_update_reason)
        )
        self.last_update_slice_id = int(
            payload.get("last_update_slice_id", self.last_update_slice_id)
        )
        self.last_top_hypothesis = str(
            payload.get("last_top_hypothesis", self.last_top_hypothesis)
        )
        self.high_ambiguity_streak = int(
            payload.get("high_ambiguity_streak", self.high_ambiguity_streak)
        )
        self.revisit_hit_count = int(payload.get("revisit_hit_count", self.revisit_hit_count))
        self.dead_end_hit_count = int(
            payload.get("dead_end_hit_count", self.dead_end_hit_count)
        )
        self.archived_paths = [
            dict(item) for item in payload.get("archived_paths", []) if isinstance(item, dict)
        ][:16]
        self.last_summary = dict(payload.get("last_summary", {}))
        config = dict(payload.get("config", {}))
        self.update_stride = max(1, int(config.get("update_stride", self.update_stride)))
        self.ambiguity_threshold = float(
            config.get("ambiguity_threshold", self.ambiguity_threshold)
        )
        self.ambiguity_streak = max(
            1,
            int(config.get("ambiguity_streak", self.ambiguity_streak)),
        )
        self.accuracy_threshold = float(
            config.get("accuracy_threshold", self.accuracy_threshold)
        )
        self.adapter.accuracy_threshold = self.accuracy_threshold
        assistance_mode = str(config.get("assistance_mode", self.assistance_mode)).lower()
        if assistance_mode in WORLD_MODEL_ASSISTANCE_MODES:
            self.assistance_mode = assistance_mode
        self.assistance_confidence_threshold = _clamp01(
            float(
                config.get(
                    "assistance_confidence_threshold",
                    self.assistance_confidence_threshold,
                )
            )
        )
        assistance_payload = dict(payload.get("last_assistance", {}))
        self.last_assistance = WorldModelAssistance(
            mode=(
                str(assistance_payload.get("mode", self.assistance_mode)).lower()
                if str(assistance_payload.get("mode", self.assistance_mode)).lower()
                in WORLD_MODEL_ASSISTANCE_MODES
                else self.assistance_mode
            ),
            active=bool(assistance_payload.get("active", False)),
            target=_estimate_hypothesis(assistance_payload.get("target"))
            or (
                str(assistance_payload.get("target"))
                if str(assistance_payload.get("target")) in WORLD_MODEL_HYPOTHESES
                else None
            ),
            alternative=_estimate_hypothesis(assistance_payload.get("alternative"))
            or (
                str(assistance_payload.get("alternative"))
                if str(assistance_payload.get("alternative")) in WORLD_MODEL_HYPOTHESES
                else None
            ),
            confidence=_clamp01(float(assistance_payload.get("confidence", 0.0))),
            source=str(assistance_payload.get("source", "none")),
            note=str(assistance_payload.get("note", "")),
        )

    def summary(self) -> dict[str, Any]:
        supports = {
            key: _clamp01(float(self.substrate.slow.get(key, 0.0))) for key in WORLD_MODEL_HYPOTHESES
        }
        ordered = sorted(supports.items(), key=lambda item: item[1], reverse=True)
        top_hypothesis, top_support = ordered[0]
        if (
            top_hypothesis == "unknown"
            and self.last_top_hypothesis in _KNOWN_HYPOTHESES
            and self.last_action in {"strengthen_best", "archive_path", "handoff_commit"}
            and supports[self.last_top_hypothesis] >= supports["unknown"] - 0.10
        ):
            top_hypothesis = self.last_top_hypothesis
            top_support = supports[top_hypothesis]
            ordered = sorted(
                supports.items(),
                key=lambda item: (
                    item[0] != top_hypothesis,
                    -item[1],
                ),
            )
        second_support = ordered[1][1] if len(ordered) > 1 else 0.0
        top_margin = max(0.0, top_support - second_support)
        contradiction_load = mean(self.contradiction.values()) if self.contradiction else 0.0
        prior_top = self.last_top_hypothesis if self.last_top_hypothesis in WORLD_MODEL_HYPOTHESES else "unknown"
        per_hypothesis = {
            key: {
                "support": _round4(supports[key]),
                "contradiction": _round4(self.contradiction[key]),
                "revisit_credit": _round4(self.revisit_credit[key]),
                "dead_end_penalty": _round4(self.dead_end_penalty[key]),
                "transition_affinity": _round4(self.transition_affinity.get(prior_top, {}).get(key, 0.0)),
            }
            for key in WORLD_MODEL_HYPOTHESES
        }
        return {
            "active": True,
            "top_hypothesis": top_hypothesis,
            "top_support": _round4(top_support),
            "second_support": _round4(second_support),
            "top_margin": _round4(top_margin),
            "unresolved_mass": _round4(supports["unknown"]),
            "contradiction_load": _round4(contradiction_load),
            "revisit_hit_count": int(self.revisit_hit_count),
            "dead_end_hit_count": int(self.dead_end_hit_count),
            "last_action": self.last_action,
            "last_update_slice_id": int(self.last_update_slice_id),
            "hypotheses": per_hypothesis,
            "assistance_mode": self.assistance_mode,
        }

    def _resolve_assistance(
        self,
        history: List[SliceSummary],
        observation: Dict[str, float],
        evidence: Dict[str, float],
    ) -> WorldModelAssistance:
        mode = self.assistance_mode
        if mode == "off" or not history:
            return WorldModelAssistance(mode=mode)
        current = history[-1]
        metadata = dict(current.metadata)

        explicit_target = _estimate_hypothesis(metadata.get("world_model_teacher_hypothesis"))
        if explicit_target is None:
            raw_target = str(metadata.get("world_model_teacher_hypothesis", ""))
            if raw_target in WORLD_MODEL_HYPOTHESES:
                explicit_target = raw_target
        explicit_confidence = _clamp01(float(metadata.get("world_model_teacher_confidence", 0.0)))

        ordered_sources = (
            ("teacher", explicit_target, explicit_confidence),
            (
                "sequence",
                _estimate_hypothesis(observation.get("source_sequence_estimate")),
                _clamp01(float(observation.get("source_sequence_confidence", 0.0))),
            ),
            (
                "route",
                _estimate_hypothesis(observation.get("source_route_estimate")),
                _clamp01(float(observation.get("source_route_confidence", 0.0))),
            ),
            (
                "feedback",
                _estimate_hypothesis(observation.get("source_feedback_estimate")),
                _clamp01(float(observation.get("source_feedback_confidence", 0.0))),
            ),
        )
        source = "none"
        target: str | None = None
        confidence = 0.0
        for candidate_source, hypothesis, candidate_confidence in ordered_sources:
            if hypothesis is None or candidate_confidence <= 0.0:
                continue
            source = candidate_source
            target = hypothesis
            confidence = candidate_confidence
            break
        if target is None or confidence < self.assistance_confidence_threshold:
            return WorldModelAssistance(
                mode=mode,
                active=False,
                target=target,
                confidence=confidence,
                source=source,
                note="insufficient_confidence",
            )

        alternative_scores = sorted(
            (
                (name, float(value))
                for name, value in evidence.items()
                if name not in {target, "unknown"}
            ),
            key=lambda item: item[1],
            reverse=True,
        )
        alternative = alternative_scores[0][0] if alternative_scores and alternative_scores[0][1] > 0.0 else None
        if alternative is None and self.last_top_hypothesis in _KNOWN_HYPOTHESES and self.last_top_hypothesis != target:
            alternative = self.last_top_hypothesis
        note = "teacher_signal" if source == "teacher" else "derived_from_channels"
        return WorldModelAssistance(
            mode=mode,
            active=True,
            target=target,
            alternative=alternative,
            confidence=confidence,
            source=source,
            note=note,
        )

    def _apply_assistance_to_evidence(
        self,
        evidence: Dict[str, float],
        assistance: WorldModelAssistance,
    ) -> Dict[str, float]:
        shaped = {key: _clamp01(value) for key, value in evidence.items()}
        if not assistance.active or assistance.target is None:
            return shaped
        target = assistance.target
        alternative = assistance.alternative
        confidence = _clamp01(assistance.confidence)
        if assistance.mode == "hinted":
            shaped[target] = _clamp01(max(shaped[target], 0.16) + 0.18 * confidence)
            if alternative is not None:
                shaped[alternative] = _clamp01(max(shaped[alternative], 0.08) + 0.08 * confidence)
            shaped["unknown"] = _clamp01(max(0.18, shaped["unknown"] * 0.92))
        elif assistance.mode == "guided":
            shaped[target] = _clamp01(max(shaped[target], 0.32 + 0.20 * confidence))
            if alternative is not None:
                shaped[alternative] = _clamp01(max(shaped[alternative], 0.18 + 0.10 * confidence))
            shaped["unknown"] = _clamp01(max(0.24, shaped["unknown"] * 0.90))
        elif assistance.mode == "teacher":
            for key in _KNOWN_HYPOTHESES:
                if key == target:
                    shaped[key] = _clamp01(max(shaped[key], 0.44 + 0.20 * confidence))
                elif key == alternative:
                    shaped[key] = _clamp01(max(shaped[key], 0.18 + 0.08 * confidence))
                else:
                    shaped[key] = _clamp01(min(shaped[key], 0.16))
            shaped["unknown"] = _clamp01(max(0.26, shaped["unknown"] * 0.88))
        return shaped

    def _build_hypothesis_evidence(self, observation: Dict[str, float]) -> Dict[str, float]:
        evidence = {key: 0.0 for key in WORLD_MODEL_HYPOTHESES}
        channel_specs = (
            ("source_sequence", 0.40, "source_sequence_estimate", "source_sequence_confidence"),
            ("source_route", 0.28, "source_route_estimate", "source_route_confidence"),
            ("source_feedback", 0.32, "source_feedback_estimate", "source_feedback_confidence"),
        )
        observed_hypotheses: list[str] = []
        for _, weight, estimate_key, confidence_key in channel_specs:
            confidence = _clamp01(float(observation.get(confidence_key, 0.0)))
            hypothesis = _estimate_hypothesis(observation.get(estimate_key))
            if hypothesis is None or confidence <= 0.0:
                continue
            evidence[hypothesis] += weight * confidence
            observed_hypotheses.append(hypothesis)
        if len(set(observed_hypotheses)) > 1:
            for hypothesis in set(observed_hypotheses):
                evidence[hypothesis] += 0.05
        evidence["unknown"] = _clamp01(
            0.36 * float(observation.get("slice_ambiguity", 0.0))
            + 0.24 * (1.0 - float(observation.get("transform_commitment_margin", 0.0)))
            + 0.18 * float(observation.get("open_context_count", 0.0))
            + 0.12 * (1.0 - float(observation.get("forecast_regime_accuracy", 0.0)))
            + 0.10 * float(observation.get("context_debt", 0.0))
        )
        return {key: _clamp01(value) for key, value in evidence.items()}

    def _detect_triggers(
        self,
        history: List[SliceSummary],
        observation: Dict[str, float],
        evidence: Dict[str, float],
        assistance: WorldModelAssistance,
    ) -> dict[str, bool]:
        current = history[-1]
        candidate_top = max(evidence, key=evidence.get)
        dead_end_trigger = False
        revisit_trigger = bool(observation.get("revisit_marker", 0.0) >= 0.5)
        if len(history) >= 2:
            previous = history[-2]
            floor_accuracy = _floor_accuracy(current)
            prior_floor = _floor_accuracy(previous)
            low_progress = floor_accuracy <= prior_floor + 0.02
            unresolved = evidence["unknown"] >= 0.42
            same_top = candidate_top == self.last_top_hypothesis
            dead_end_trigger = bool(
                same_top
                and low_progress
                and unresolved
                and floor_accuracy < self.accuracy_threshold
            )
        if not revisit_trigger and self.dead_end_penalty.get(candidate_top, 0.0) >= 0.18:
            revisit_trigger = True
        if observation.get("dead_end_marker", 0.0) >= 0.5:
            dead_end_trigger = True
        assisted_focus = bool(
            assistance.active
            and assistance.mode in {"guided", "teacher"}
            and assistance.target is not None
            and self.last_top_hypothesis not in {"unknown", assistance.target}
        )
        return {
            "high_ambiguity": self.high_ambiguity_streak >= self.ambiguity_streak,
            "dead_end": dead_end_trigger,
            "revisit": revisit_trigger,
            "assisted_focus": assisted_focus,
        }

    def _should_update(self, slice_id: int, triggers: dict[str, bool]) -> tuple[bool, str]:
        if triggers["dead_end"]:
            return True, "dead_end"
        if triggers["revisit"]:
            return True, "revisit"
        if triggers["high_ambiguity"]:
            return True, "high_ambiguity"
        if slice_id % self.update_stride == 0:
            return True, "cadence"
        if self.last_update_slice_id <= 0:
            return True, "bootstrap"
        return False, "defer"

    def _candidate_scores(
        self,
        evidence: Dict[str, float],
    ) -> Dict[str, float]:
        prior_top = self.last_top_hypothesis if self.last_top_hypothesis in WORLD_MODEL_HYPOTHESES else "unknown"
        scores: Dict[str, float] = {}
        for key in WORLD_MODEL_HYPOTHESES:
            scores[key] = _clamp01(
                0.55 * float(self.substrate.slow.get(key, 0.0))
                + 0.45 * float(evidence.get(key, 0.0))
                + 0.20 * float(self.revisit_credit.get(key, 0.0))
                + 0.15 * float(self.transition_affinity.get(prior_top, {}).get(key, 0.0))
                - 0.35 * float(self.dead_end_penalty.get(key, 0.0))
                - 0.22 * float(self.contradiction.get(key, 0.0))
            )
        return scores

    def _select_action(
        self,
        observation: Dict[str, float],
        evidence: Dict[str, float],
        triggers: dict[str, bool],
        assistance: WorldModelAssistance,
    ) -> str:
        scores = self._candidate_scores(evidence)
        ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        top_hypothesis, top_score = ordered[0]
        second_hypothesis, second_score = ordered[1]
        top_margin = max(0.0, top_score - second_score)
        unresolved_mass = evidence["unknown"]
        if assistance.active and assistance.target is not None:
            target = assistance.target
            if assistance.mode == "guided":
                if triggers["dead_end"] and self.last_top_hypothesis not in {"unknown", target}:
                    return "mark_dead_end"
                if top_hypothesis != target and second_hypothesis == target:
                    return "reopen_alternative"
                return "hold_open"
            elif assistance.mode == "teacher":
                if triggers["dead_end"] and self.last_top_hypothesis not in {"unknown", target}:
                    return "mark_dead_end"
                if top_hypothesis != target and second_hypothesis == target:
                    return "reopen_alternative"
                return "hold_open"
        if (
            triggers["dead_end"]
            and self.last_top_hypothesis in WORLD_MODEL_HYPOTHESES
            and self.last_top_hypothesis != "unknown"
        ):
            return "mark_dead_end"
        if triggers["revisit"] and second_hypothesis != "unknown":
            return "reopen_alternative"
        if (
            unresolved_mass >= 0.40
            or top_margin <= 0.12
            or observation["slice_ambiguity"] >= self.ambiguity_threshold
        ):
            return "hold_open"
        if (
            top_margin >= 0.22
            and unresolved_mass <= 0.28
            and observation["floor_accuracy"] >= 0.78
        ):
            return "archive_path"
        if (
            top_margin >= 0.24
            and unresolved_mass <= 0.32
            and observation["transform_commitment_margin"] >= 0.55
        ):
            return "handoff_commit"
        if top_hypothesis != "unknown" and top_margin >= 0.14:
            return "strengthen_best"
        return "hold_open"

    def _apply_action(
        self,
        action: str,
        evidence: Dict[str, float],
        observation: Dict[str, float],
        triggers: dict[str, bool],
        slice_id: int,
        assistance: WorldModelAssistance,
    ) -> None:
        for key in WORLD_MODEL_HYPOTHESES:
            self.substrate.fast[key] = evidence.get(key, 0.0)
            self.contradiction[key] *= 0.92
            self.revisit_credit[key] *= 0.90
            self.dead_end_penalty[key] *= 0.95
            for inner in WORLD_MODEL_HYPOTHESES:
                self.transition_affinity[key][inner] *= 0.96
        channels = []
        for estimate_key, confidence_key in (
            ("source_sequence_estimate", "source_sequence_confidence"),
            ("source_route_estimate", "source_route_confidence"),
            ("source_feedback_estimate", "source_feedback_confidence"),
        ):
            hypothesis = _estimate_hypothesis(observation.get(estimate_key))
            confidence = _clamp01(float(observation.get(confidence_key, 0.0)))
            if hypothesis is not None and confidence > 0.0:
                channels.append((hypothesis, confidence))
        if len({hypothesis for hypothesis, _ in channels}) > 1:
            for hypothesis, confidence in channels:
                self.contradiction[hypothesis] = _clamp01(
                    self.contradiction[hypothesis] + 0.12 * confidence
                )
        if assistance.active and assistance.target is not None and assistance.mode in {"guided", "teacher"}:
            for key in _KNOWN_HYPOTHESES:
                if key == assistance.target:
                    self.revisit_credit[key] = _clamp01(
                        self.revisit_credit[key] + 0.08 * assistance.confidence
                    )
                    self.dead_end_penalty[key] = _clamp01(self.dead_end_penalty[key] * 0.78)
                else:
                    self.contradiction[key] = _clamp01(
                        self.contradiction[key]
                        + 0.04 * assistance.confidence * (1.0 if evidence.get(key, 0.0) > 0.0 else 0.0)
                    )

        scores = self._candidate_scores(evidence)
        ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        top_hypothesis, top_score = ordered[0]
        second_hypothesis, second_score = ordered[1]
        dead_end_target = (
            self.last_top_hypothesis
            if action == "mark_dead_end"
            and self.last_top_hypothesis in WORLD_MODEL_HYPOTHESES
            and self.last_top_hypothesis != "unknown"
            else top_hypothesis
        )
        prior_top = self.last_top_hypothesis if self.last_top_hypothesis in WORLD_MODEL_HYPOTHESES else "unknown"
        self.transition_affinity[prior_top][top_hypothesis] = _clamp01(
            self.transition_affinity[prior_top][top_hypothesis] + 0.16 * top_score
        )
        if triggers["revisit"] and top_hypothesis in WORLD_MODEL_HYPOTHESES:
            self.revisit_hit_count += 1
            self.revisit_credit[top_hypothesis] = _clamp01(
                self.revisit_credit[top_hypothesis] + 0.18
            )
        if action == "hold_open":
            for key in _KNOWN_HYPOTHESES:
                plausible = evidence[key] >= 0.10 or key in {top_hypothesis, second_hypothesis}
                if plausible:
                    self.substrate.slow[key] = _clamp01(
                        max(self.substrate.slow.get(key, 0.0), 0.12) + 0.18 * evidence[key]
                    )
            self.substrate.slow["unknown"] = _clamp01(
                max(self.substrate.slow.get("unknown", 0.0), evidence["unknown"])
            )
        elif action == "strengthen_best":
            self.substrate.slow[top_hypothesis] = _clamp01(
                self.substrate.slow.get(top_hypothesis, 0.0) + 0.34 + 0.28 * evidence[top_hypothesis]
            )
            self.substrate.slow[second_hypothesis] = _clamp01(
                self.substrate.slow.get(second_hypothesis, 0.0) + 0.10 * second_score
            )
            self.substrate.slow["unknown"] = _clamp01(
                self.substrate.slow.get("unknown", 0.0) * 0.76
            )
        elif action == "reopen_alternative":
            self.substrate.slow[top_hypothesis] = _clamp01(
                self.substrate.slow.get(top_hypothesis, 0.0) * 0.92
            )
            self.substrate.slow[second_hypothesis] = _clamp01(
                self.substrate.slow.get(second_hypothesis, 0.0) + 0.22 + 0.16 * second_score
            )
            self.revisit_credit[second_hypothesis] = _clamp01(
                self.revisit_credit[second_hypothesis] + 0.20
            )
            self.substrate.slow["unknown"] = _clamp01(
                max(self.substrate.slow.get("unknown", 0.0), 0.18)
            )
        elif action == "mark_dead_end":
            self.dead_end_hit_count += 1
            self.dead_end_penalty[dead_end_target] = _clamp01(
                self.dead_end_penalty[dead_end_target] + 0.30
            )
            self.substrate.slow[dead_end_target] = _clamp01(
                self.substrate.slow.get(dead_end_target, 0.0) * 0.42
            )
            self.substrate.slow["unknown"] = _clamp01(
                max(self.substrate.slow.get("unknown", 0.0), 0.22)
            )
        elif action == "archive_path":
            self.archived_paths.append(
                {
                    "slice_id": int(slice_id),
                    "top_hypothesis": top_hypothesis,
                    "support": _round4(top_score),
                    "floor_accuracy": _round4(observation["floor_accuracy"]),
                }
            )
            self.archived_paths = self.archived_paths[-16:]
            self.substrate.slow[top_hypothesis] = _clamp01(
                self.substrate.slow.get(top_hypothesis, 0.0) + 0.42 + 0.24 * top_score
            )
            self.substrate.slow["unknown"] = _clamp01(
                self.substrate.slow.get("unknown", 0.0) * 0.52
            )
        elif action == "handoff_commit":
            self.substrate.slow[top_hypothesis] = _clamp01(
                self.substrate.slow.get(top_hypothesis, 0.0) + 0.48 + 0.30 * top_score
            )
            self.substrate.slow["unknown"] = _clamp01(
                self.substrate.slow.get("unknown", 0.0) * 0.44
            )
        self.substrate.tick()
        self.last_action = action
        self.last_update_reason = action
        self.last_update_slice_id = int(slice_id)
        self.last_top_hypothesis = top_hypothesis
