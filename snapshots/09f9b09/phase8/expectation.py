from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from real_core.types import CycleEntry, LocalPrediction, PredictionError, RecognitionState

ROUTE_TRANSFORMS = ("identity", "rotate_left_1", "xor_mask_1010", "xor_mask_0101")


def _route_neighbor(action: str) -> str | None:
    if action.startswith("route_transform:"):
        parts = action.split(":")
        if len(parts) == 3:
            return parts[1]
        return None
    if action.startswith("route:"):
        return action.split(":", 1)[1]
    return None


def _route_transform(action: str) -> str:
    if action.startswith("route_transform:"):
        parts = action.split(":")
        if len(parts) == 3:
            return parts[2]
    return "identity"


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


@dataclass
class Phase8ExpectationModel:
    """Small source-local expectation binding for Phase 8 routing actions."""

    environment: object
    node_id: str

    def predict(
        self,
        state_before: Dict[str, float],
        available: List[str],
        history: List[CycleEntry],
        *,
        recognition: RecognitionState | None = None,
        prior_coherence: float | None = None,
        substrate=None,
    ) -> Dict[str, LocalPrediction]:
        predictions: Dict[str, LocalPrediction] = {}
        for action in available:
            neighbor_id = _route_neighbor(action)
            if neighbor_id is None:
                continue
            prediction = self._predict_route_action(
                action,
                neighbor_id,
                transform_name=_route_transform(action),
                state_before=state_before,
                history=history,
                recognition=recognition,
                prior_coherence=prior_coherence,
                substrate=substrate,
            )
            predictions[action] = prediction
        return predictions

    def compare(
        self,
        action: str,
        prediction: LocalPrediction | None,
        state_after: Dict[str, float],
        dimensions: Dict[str, float],
        coherence: float,
        delta: float,
        history: List[CycleEntry],
    ) -> PredictionError | None:
        if prediction is None:
            return None
        neighbor_id = _route_neighbor(action)
        outcome_error: Dict[str, float] = {}
        if neighbor_id is not None:
            expected_progress = float(
                prediction.expected_outcome.get("progress", 0.0)
            )
            actual_progress = float(state_after.get(f"progress_{neighbor_id}", 0.0))
            outcome_error["progress"] = actual_progress - expected_progress
        if "match_ratio" in prediction.expected_outcome:
            expected_match_ratio = float(
                prediction.expected_outcome.get("match_ratio", 0.0)
            )
            actual_match_ratio = float(state_after.get("last_match_ratio", 0.0))
            outcome_error["match_ratio"] = actual_match_ratio - expected_match_ratio
        coherence_error = (
            None
            if prediction.expected_coherence is None
            else coherence - prediction.expected_coherence
        )
        delta_error = (
            None if prediction.expected_delta is None else delta - prediction.expected_delta
        )
        magnitude = sum(abs(value) for value in outcome_error.values())
        if coherence_error is not None:
            magnitude += abs(coherence_error)
        if delta_error is not None:
            magnitude += abs(delta_error)
        return PredictionError(
            outcome_error=outcome_error,
            coherence_error=coherence_error,
            delta_error=delta_error,
            magnitude=magnitude,
            metadata={
                "source": "phase8_expectation",
                "action": action,
                "node_id": self.node_id,
            },
        )

    def _predict_route_action(
        self,
        action: str,
        neighbor_id: str,
        *,
        transform_name: str,
        state_before: Dict[str, float],
        history: List[CycleEntry],
        recognition: RecognitionState | None,
        prior_coherence: float | None,
        substrate,
    ) -> LocalPrediction:
        context_weight = (
            _clamp(float(state_before.get("effective_context_confidence", 0.0)))
            if state_before.get("effective_has_context", 0.0) >= 0.5
            else 0.0
        )
        progress = float(state_before.get(f"progress_{neighbor_id}", 0.0))
        congestion = float(state_before.get(f"congestion_{neighbor_id}", 0.0))
        inhibited = float(state_before.get(f"inhibited_{neighbor_id}", 0.0))
        support = float(state_before.get(f"support_{neighbor_id}", 0.0))
        action_support = float(
            state_before.get(
                f"action_support_{neighbor_id}_{transform_name}",
                support,
            )
        )
        task_transform_affinity = float(
            state_before.get(f"task_transform_affinity_{transform_name}", 0.0)
        )
        source_sequence_hint = float(
            state_before.get(f"source_sequence_transform_hint_{transform_name}", 0.0)
        )
        history_transform_evidence = float(
            state_before.get(f"history_transform_evidence_{transform_name}", 0.0)
        )
        feedback_credit = float(
            state_before.get(f"feedback_credit_{transform_name}", 0.0)
        )
        feedback_debt = float(state_before.get(f"feedback_debt_{transform_name}", 0.0))
        context_feedback_credit = float(
            state_before.get(f"context_feedback_credit_{transform_name}", 0.0)
        )
        context_feedback_debt = float(
            state_before.get(f"context_feedback_debt_{transform_name}", 0.0)
        )
        source_sequence_available = float(
            state_before.get("source_sequence_available", 0.0)
        )
        source_sequence_confidence = float(
            state_before.get("source_sequence_context_confidence", 0.0)
        )
        latent_available = float(state_before.get("latent_context_available", 0.0))
        latent_confidence = float(state_before.get("latent_context_confidence", 0.0))
        contradiction_pressure = float(
            state_before.get("contradiction_pressure", 0.0)
        )
        transfer_adaptation_phase = _clamp(
            float(state_before.get("transfer_adaptation_phase", 0.0))
        )
        hidden_task_commitment = (
            state_before.get("head_has_task", 0.0) >= 0.5
            and state_before.get("head_has_context", 0.0) < 0.5
            and state_before.get("effective_has_context", 0.0) < 0.5
        )
        route_drive = (
            0.38 * progress
            + 0.22 * support
            + 0.16 * action_support
            - 0.24 * congestion
            - 0.22 * inhibited
        )
        transform_drive = (
            0.24 * history_transform_evidence
            + 0.24 * feedback_credit
            + 0.18 * context_feedback_credit * context_weight
            - 0.24 * feedback_debt
            - 0.26 * context_feedback_debt * context_weight
        )
        if hidden_task_commitment:
            transform_drive += 0.18 * max(0.0, task_transform_affinity)
            transform_drive += 0.32 * max(0.0, source_sequence_hint)
            transform_drive -= 0.18 * max(0.0, -task_transform_affinity)
            transform_drive -= 0.22 * max(0.0, -source_sequence_hint)
            if transform_name == "identity":
                transform_drive -= 0.14 + 0.06 * source_sequence_available
        elif task_transform_affinity > 0.0:
            transform_drive += 0.10 * task_transform_affinity
        elif task_transform_affinity < 0.0:
            transform_drive -= 0.08 * abs(task_transform_affinity)

        recognition_alignment = self._recognition_alignment(
            neighbor_id,
            transform_name,
            recognition,
            substrate,
        )
        stale_family_risk = self._stale_family_risk(
            transform_name=transform_name,
            state_before=state_before,
            history=history,
            hidden_task_commitment=hidden_task_commitment,
            transfer_adaptation_phase=transfer_adaptation_phase,
            feedback_debt=feedback_debt,
            context_feedback_debt=context_feedback_debt,
        )
        evidence_strength = _clamp(
            0.32 * max(0.0, history_transform_evidence)
            + 0.24 * max(0.0, feedback_credit)
            + 0.14 * max(0.0, context_feedback_credit) * context_weight
            + 0.28 * max(0.0, source_sequence_hint)
            + 0.12 * source_sequence_confidence
            + 0.10 * latent_available * latent_confidence
            + 0.10 * max(0.0, recognition_alignment)
        )
        ambiguity = _clamp(
            0.24 * contradiction_pressure
            + 0.18 * transfer_adaptation_phase
            + 0.12 * (1.0 - context_weight)
        )
        confidence = _clamp(
            0.18
            + 0.42 * evidence_strength
            + 0.18 * max(0.0, route_drive)
            + 0.12 * max(0.0, recognition_alignment)
            - 0.12 * ambiguity
        )
        uncertainty = _clamp(
            1.0
            - confidence
            + 0.10 * contradiction_pressure
            + 0.06 * max(0.0, -recognition_alignment)
        )
        expected_delta = max(
            -0.45,
            min(
                0.45,
                0.26 * route_drive
                + 0.28 * transform_drive
                + 0.12 * recognition_alignment
                - 0.14 * stale_family_risk
                - 0.08 * uncertainty,
            ),
        )
        baseline_coherence = 0.5 if prior_coherence is None else float(prior_coherence)
        expected_coherence = _clamp(baseline_coherence + 0.30 * expected_delta)
        expected_progress = _clamp(
            progress
            + 0.22 * support
            + 0.12 * max(0.0, expected_delta)
            - 0.16 * congestion
        )
        expected_match_ratio = _clamp(
            float(state_before.get("last_match_ratio", 0.0))
            + 0.28 * max(0.0, transform_drive)
            + 0.08 * max(0.0, recognition_alignment)
            - 0.18 * max(0.0, -transform_drive)
        )
        return LocalPrediction(
            expected_outcome={
                "progress": expected_progress,
                "match_ratio": expected_match_ratio,
                "neighbor_id": neighbor_id,
                "transform_name": transform_name,
            },
            expected_coherence=expected_coherence,
            expected_delta=expected_delta,
            confidence=confidence,
            uncertainty=uncertainty,
            metadata={
                "source": "phase8_expectation",
                "node_id": self.node_id,
                "hidden_task_commitment": hidden_task_commitment,
                "recognition_alignment": round(recognition_alignment, 6),
                "route_drive": round(route_drive, 6),
                "transform_drive": round(transform_drive, 6),
                "stale_family_risk": round(stale_family_risk, 6),
            },
        )

    def _stale_family_risk(
        self,
        *,
        transform_name: str,
        state_before: Dict[str, float],
        history: List[CycleEntry],
        hidden_task_commitment: bool,
        transfer_adaptation_phase: float,
        feedback_debt: float,
        context_feedback_debt: float,
    ) -> float:
        if not hidden_task_commitment:
            return 0.0
        recent_commitment = self._recent_transform_commitment(history, transform_name)
        current_alignment = self._transform_alignment(transform_name, state_before)
        best_alternative_alignment = max(
            (
                self._transform_alignment(candidate, state_before)
                for candidate in ROUTE_TRANSFORMS
                if candidate != transform_name
            ),
            default=0.0,
        )
        alignment_gap = max(0.0, best_alternative_alignment - current_alignment)
        debt_pressure = 0.45 * feedback_debt + 0.55 * context_feedback_debt
        return _clamp(
            (0.42 * recent_commitment + 0.40 * alignment_gap + 0.28 * debt_pressure)
            * (0.60 + 0.40 * transfer_adaptation_phase)
        )

    def _recent_transform_commitment(
        self,
        history: List[CycleEntry],
        transform_name: str,
        *,
        window: int = 6,
    ) -> float:
        route_entries = [
            entry
            for entry in history
            if _route_neighbor(str(entry.action)) is not None
        ]
        if not route_entries:
            return 0.0
        recent = route_entries[-window:]
        matching = sum(
            1
            for entry in recent
            if _route_transform(str(entry.action)) == transform_name
        )
        return matching / max(1, len(recent))

    def _transform_alignment(
        self,
        transform_name: str,
        state_before: Dict[str, float],
    ) -> float:
        task_affinity = float(
            state_before.get(f"task_transform_affinity_{transform_name}", 0.0)
        )
        sequence_hint = float(
            state_before.get(f"source_sequence_transform_hint_{transform_name}", 0.0)
        )
        history_evidence = float(
            state_before.get(f"history_transform_evidence_{transform_name}", 0.0)
        )
        return _clamp(
            0.45 * max(0.0, task_affinity)
            + 0.40 * max(0.0, sequence_hint)
            + 0.25 * max(0.0, history_evidence)
            - 0.25 * max(0.0, -task_affinity)
            - 0.30 * max(0.0, -sequence_hint)
        )

    def _recognition_alignment(
        self,
        neighbor_id: str,
        transform_name: str,
        recognition: RecognitionState | None,
        substrate,
    ) -> float:
        if recognition is None or not recognition.matches or substrate is None:
            return 0.0
        target_signature = (neighbor_id, transform_name)
        total = 0.0
        for match in recognition.matches:
            pattern_index = match.metadata.get("pattern_index")
            if not isinstance(pattern_index, int):
                continue
            patterns = getattr(substrate, "constraint_patterns", [])
            if pattern_index < 0 or pattern_index >= len(patterns):
                continue
            pattern = patterns[pattern_index]
            weight = _clamp(
                recognition.confidence
                * match.score
                * max(0.25, float(getattr(pattern, "strength", 0.0))),
            )
            if match.source in ("route_attractor", "route_trough"):
                focused_neighbor = self._pattern_focus_neighbor(substrate, pattern, match.source)
                if focused_neighbor == neighbor_id:
                    total += weight if match.source == "route_attractor" else -weight
            if match.source in (
                "transform_attractor",
                "context_transform_attractor",
                "transform_trough",
                "context_transform_trough",
            ):
                focused_key = self._pattern_focus_action_key(pattern, match.source)
                if focused_key is None:
                    continue
                focused_signature = self._action_signature_from_key(focused_key)
                if focused_signature == target_signature:
                    if "trough" in match.source:
                        total -= weight
                    else:
                        total += weight
        return max(-1.0, min(1.0, total))

    def _pattern_focus_neighbor(self, substrate, pattern, source: str) -> str | None:
        scored_neighbors: list[tuple[float, str]] = []
        for neighbor_id in getattr(substrate, "neighbor_ids", ()):
            key = substrate.edge_key(neighbor_id)
            if key not in pattern.dim_scores:
                continue
            scored_neighbors.append((float(pattern.dim_scores[key]), neighbor_id))
        if not scored_neighbors:
            return None
        if source == "route_trough" or getattr(pattern, "valence", 0.0) < 0.0:
            return min(scored_neighbors, key=lambda item: item[0])[1]
        return max(scored_neighbors, key=lambda item: item[0])[1]

    def _pattern_focus_action_key(self, pattern, source: str) -> str | None:
        action_scores = [
            (float(value), str(key))
            for key, value in pattern.dim_scores.items()
            if str(key).startswith("action:") or str(key).startswith("context_action:")
        ]
        if not action_scores:
            return None
        if "trough" in source or getattr(pattern, "valence", 0.0) < 0.0:
            return min(action_scores, key=lambda item: item[0])[1]
        return max(action_scores, key=lambda item: item[0])[1]

    def _action_signature_from_key(self, key: str) -> tuple[str, str] | None:
        if key.startswith("action:"):
            parts = key.split(":")
            if len(parts) == 3:
                return parts[1], parts[2]
            return None
        if key.startswith("context_action:"):
            parts = key.split(":")
            if len(parts) == 4:
                return parts[1], parts[2]
            return None
        return None
