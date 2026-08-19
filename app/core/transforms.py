"""Canonical feature transformations shared by training, inference, and evaluation.

Every feature transformation used by the ML model MUST be defined here.
Training, inference, and evaluation scripts import from this module to
guarantee train/serve consistency.

The 11 call-behavior features consumed by the deployed model are:

    Raw inputs (6):
        call_duration_min, is_unknown_number, is_video_call,
        hour_of_day, caller_call_history, outgoing_activity_ratio

    Derived (5):
        is_weekend, call_duration_log, is_early_morning,
        is_late_night, activity_category
"""

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

# ---------------------------------------------------------------------------
# ML feature schema — the 11 features the model consumes.
# This tuple IS the feature contract. Training, inference, and evaluation
# must produce/exactly this ordering.
# ---------------------------------------------------------------------------

ML_FEATURE_NAMES: tuple[str, ...] = (
    "call_duration_min",
    "is_unknown_number",
    "is_video_call",
    "hour_of_day",
    "caller_call_history",
    "outgoing_activity_ratio",
    "is_weekend",
    "call_duration_log",
    "is_early_morning",
    "is_late_night",
    "activity_category",
)

# ---------------------------------------------------------------------------
# Canonical thresholds — single source of truth.
# These MUST be used by training, inference, and evaluation.
# ---------------------------------------------------------------------------

ACTIVITY_CATEGORY_LOW = 0.33
ACTIVITY_CATEGORY_HIGH = 0.66

EARLY_MORNING_LOW = 5
EARLY_MORNING_HIGH = 8

LATE_NIGHT_START = 22
LATE_NIGHT_END = 4


# ---------------------------------------------------------------------------
# Canonical transformations
# ---------------------------------------------------------------------------

def bin_activity_category(outgoing_activity_ratio: float) -> int:
    """Discretise outgoing_activity_ratio into 3 ordinal bins.

    < 0.33  -> 0  (low activity — isolation signal)
    < 0.66  -> 1  (moderate activity)
    >= 0.66 -> 2  (high activity — normal behaviour)

    This function is the SINGLE definition used by both training and
    inference.  Never duplicate this logic elsewhere.
    """
    if outgoing_activity_ratio < ACTIVITY_CATEGORY_LOW:
        return 0
    elif outgoing_activity_ratio < ACTIVITY_CATEGORY_HIGH:
        return 1
    else:
        return 2


def compute_is_weekend(day_of_week: int | None, is_weekend: bool | None = None) -> int:
    """Derive is_weekend from day_of_week or an explicit weekend flag.

    If day_of_week is provided, Saturday=5 and Sunday=6 are weekends.
    If only is_weekend is provided, use that directly.
    If neither is provided, default to 0 (unknown — never fabricate).
    """
    if day_of_week is not None:
        return 1 if day_of_week in (5, 6) else 0
    if is_weekend is not None:
        return 1 if is_weekend else 0
    return 0


def compute_call_duration_log(call_duration_min: float) -> float:
    """log1p transform of call duration. Always >= 0."""
    return math.log1p(max(0.0, call_duration_min))


def compute_is_early_morning(hour_of_day: int) -> int:
    """1 if hour is in the early-morning band [5, 8], else 0."""
    return 1 if EARLY_MORNING_LOW <= hour_of_day <= EARLY_MORNING_HIGH else 0


def compute_is_late_night(hour_of_day: int) -> int:
    """1 if hour is in the late-night band [22, 23, 0, 1, 2, 3, 4], else 0."""
    return 1 if (hour_of_day >= LATE_NIGHT_START or hour_of_day <= LATE_NIGHT_END) else 0


def _coerce_float(value: Any, default: float = 0.0) -> float:
    """Safely coerce a value to float, treating None and missing as default.

    This handles the case where a key exists in a dict with value None —
    raw.get("key", default) would return None in that scenario, but we
    always want the default for None/missing values.
    """
    if value is None:
        return float(default)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return float(default)
        try:
            return float(text)
        except ValueError:
            return float(default)
    return float(default)


def _coerce_int(value: Any, default: int | None = 0) -> int | None:
    """Safely coerce a value to int, treating None and missing as default.

    If default is None, returns None for missing/non-coercible values.
    """
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return int(round(value))
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return default
        try:
            return int(round(float(text)))
        except ValueError:
            return default
    return default


# ---------------------------------------------------------------------------
# Bulk derivation: raw dict -> 11-feature dict (for inference)
# ---------------------------------------------------------------------------

def derive_ml_features(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Given a raw call-behaviour payload, return a dict of exactly the 11
    ML features in canonical order.

    This is the inference-time entry point used by RiskEngine.  It mirrors
    the derivation logic used during training so both paths are identical.

    Handles None/missing values safely — never raises on None inputs.
    """
    call_duration = _coerce_float(raw.get("call_duration_min") or raw.get("call_duration_minutes"), 0.0)
    if call_duration < 0:
        call_duration = 0.0

    is_unknown = int(bool(_coerce_int(raw.get("is_unknown_number"), 0)))
    is_video = int(bool(_coerce_int(raw.get("is_video_call"), 0)))

    hour = _coerce_int(raw.get("hour_of_day"), 12)
    hour = max(0, min(23, hour))

    caller_history = _coerce_int(raw.get("caller_call_history"), 0)

    activity = _coerce_float(raw.get("outgoing_activity_ratio"), 0.5)
    activity = max(0.0, min(1.0, activity))

    day_of_week = raw.get("day_of_week")
    is_weekend_raw = raw.get("is_weekend")
    is_weekend = compute_is_weekend(
        day_of_week=_coerce_int(day_of_week, None) if day_of_week is not None else None,
        is_weekend=bool(is_weekend_raw) if is_weekend_raw is not None else None,
    )

    return {
        "call_duration_min": round(call_duration, 3),
        "is_unknown_number": is_unknown,
        "is_video_call": is_video,
        "hour_of_day": hour,
        "caller_call_history": caller_history,
        "outgoing_activity_ratio": round(activity, 3),
        "is_weekend": is_weekend,
        "call_duration_log": round(compute_call_duration_log(call_duration), 3),
        "is_early_morning": compute_is_early_morning(hour),
        "is_late_night": compute_is_late_night(hour),
        "activity_category": bin_activity_category(activity),
    }


# ---------------------------------------------------------------------------
# Bulk derivation for training/evaluation DataFrames
# ---------------------------------------------------------------------------

def derive_ml_features_from_row(row: Mapping[str, Any]) -> dict[str, Any]:
    """Derive the 11 ML features from a single row mapping.

    Identical to derive_ml_features but accepts row-style inputs where
    the key may be 'duration_minutes' or 'call_duration_minutes'.
    """
    merged = dict(row)
    # Normalise duration key
    if "call_duration_min" not in merged:
        for key in ("duration_minutes", "call_duration_minutes"):
            if key in merged:
                merged["call_duration_min"] = merged.pop(key)
                break
    return derive_ml_features(merged)


def add_derived_columns(df: "pd.DataFrame") -> "pd.DataFrame":  # noqa: F821
    """Add the 5 derived ML columns to a pandas DataFrame.

    Used by training and evaluation scripts.  Applies exactly the same
    thresholds as derive_ml_features / bin_activity_category.
    """
    import pandas as pd

    df = df.copy()
    df["call_duration_log"] = df["call_duration_min"].clip(lower=0).apply(math.log1p).round(3)
    df["is_early_morning"] = ((df["hour_of_day"] >= EARLY_MORNING_LOW) & (df["hour_of_day"] <= EARLY_MORNING_HIGH)).astype(int)
    df["is_late_night"] = ((df["hour_of_day"] >= LATE_NIGHT_START) | (df["hour_of_day"] <= LATE_NIGHT_END)).astype(int)
    df["activity_category"] = df["outgoing_activity_ratio"].apply(bin_activity_category).astype(int)
    # is_weekend derived from day_of_week if present, else from existing column
    if "day_of_week" in df.columns:
        df["is_weekend"] = df["day_of_week"].isin([5, 6]).astype(int)
    elif "is_weekend" not in df.columns:
        df["is_weekend"] = 0
    else:
        df["is_weekend"] = df["is_weekend"].astype(int)
    return df
