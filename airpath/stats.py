"""Phase 1 source scores: accuracy, severity mix, suitability."""

from __future__ import annotations

import math
from collections import defaultdict

from .models import (
    THRESHOLDS,
    FORECAST_PRODUCTS,
    PointVerification,
    Severity,
    Source,
    SourceScore,
    Variable,
)
from .verify import holds_true

MIN_N_FOR_PHASE2 = 6
SUITABILITY_GATE = 0.55


def _rmse(values: list[float]) -> float:
    if not values:
        return 0.0
    return math.sqrt(sum(v * v for v in values) / len(values))


def suitability(hit_rate: float, rmse: float, holds_threshold: float, n: int) -> float:
    """0–1 score: accuracy × sample support. Higher is more usable for routing."""
    if n <= 0:
        return 0.0
    acc = math.exp(-rmse / max(holds_threshold, 1e-6))
    support = min(1.0, n / 12.0)
    return max(0.0, min(1.0, 0.55 * acc + 0.30 * hit_rate + 0.15 * support))


def score_verifications(results: list[PointVerification]) -> list[SourceScore]:
    groups: dict[tuple[Source, Source, Variable], list[PointVerification]] = defaultdict(list)
    for r in results:
        truth = r.truth_source or r.source
        groups[(r.source, truth, r.variable)].append(r)

    scores: list[SourceScore] = []
    for (source, truth, variable), rows in sorted(
        groups.items(), key=lambda kv: (kv[0][0].value, kv[0][1].value, kv[0][2].value)
    ):
        n = len(rows)
        errors = [r.error for r in rows]
        abs_errors = [r.abs_error for r in rows]
        corr_errors = [r.corrected_error for r in rows]
        mae = sum(abs_errors) / n
        rmse = _rmse(errors)
        bias = sum(errors) / n
        hit = sum(1 for r in rows if r.holds_true) / n
        mild = sum(1 for r in rows if r.severity is Severity.MILD)
        moderate = sum(1 for r in rows if r.severity is Severity.MODERATE)
        severe = sum(1 for r in rows if r.severity is Severity.SEVERE)
        rmse_corr = _rmse(corr_errors)
        hit_corr = sum(1 for r in rows if holds_true(variable, abs(r.corrected_error))) / n
        # Suitability is after the improvement equation: a biased but
        # correctable source is usable in Phase 2.
        suit = suitability(hit_corr, rmse_corr, THRESHOLDS[variable]["holds"], n)
        eq = rows[0].equation
        scores.append(
            SourceScore(
                source=source,
                variable=variable,
                n=n,
                mae=mae,
                rmse=rmse,
                bias=bias,
                hit_rate=hit,
                mild=mild,
                moderate=moderate,
                severe=severe,
                suitability=suit,
                suitable_for_phase2=suit >= SUITABILITY_GATE and n >= MIN_N_FOR_PHASE2,
                equation=eq,
                rmse_corrected=rmse_corr,
                truth_source=truth,
            )
        )
    return scores


def phase1_ready(scores: list[SourceScore]) -> bool:
    """Phase 2 needs a suitable forecast-product wind or temperature score."""
    return any(
        s.suitable_for_phase2
        and s.source in FORECAST_PRODUCTS
        and s.variable in {Variable.WIND_KT, Variable.TEMP_C}
        for s in scores
    )


def summarize(scores: list[SourceScore]) -> dict:
    return {
        "phase1_ready": phase1_ready(scores),
        "suitable_count": sum(1 for s in scores if s.suitable_for_phase2),
        "sources": [s.to_dict() for s in scores],
    }
