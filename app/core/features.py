from __future__ import annotations

import math

from typing import Any, Dict, Mapping


# The six raw call-behavior fields accepted by the scoring API. These are a
# subset of the 11-feature ML schema (the remaining 5 ML features are derived
# inside extract_features()).
CALL_BEHAVIOR_FIELDS = (
    "call_duration_min",
    "is_unknown_number",
    "is_video_call",
    "hour_of_day",
    "caller_call_history",
    "outgoing_activity_ratio",
)

# Telemetry-only fields captured by the device/Android layer. None of these
# belong to the deployed 11-feature call-behavior model schema.
TELEMETRY_FIELDS = (
    "screen_time_on_call_percent",
    "num_app_switches",
    "num_home_presses",
    "has_sms_activity",
    "has_social_app_activity",
    "location_change",
    "screen_brightness",
    "screen_on_continuous_hours",
    "persistence_hours",
)

TELEMETRY_MISSING_FLAGS = tuple(f"is_missing_{name}" for name in TELEMETRY_FIELDS)

# Every feature that must be excluded from ML inference. Missing telemetry is
# represented by the is_missing_* flags (consumed by the safety-rule layer),
# never by an observed 0.0/False fed into the model.
MODEL_EXCLUDED_FEATURES = frozenset(TELEMETRY_FIELDS + TELEMETRY_MISSING_FLAGS)


def canonical_feature_names() -> list[str]:
    """Return the canonical feature ordering used by the risk engine."""
    return [
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
        "screen_time_on_call_percent",
        "num_app_switches",
        "num_home_presses",
        "has_sms_activity",
        "has_social_app_activity",
        "location_change",
        "screen_brightness",
        "screen_on_continuous_hours",
        "persistence_hours",
        "is_missing_screen_time_on_call_percent",
        "is_missing_num_app_switches",
        "is_missing_num_home_presses",
        "is_missing_has_sms_activity",
        "is_missing_has_social_app_activity",
        "is_missing_location_change",
        "is_missing_screen_brightness",
        "is_missing_screen_on_continuous_hours",
        "is_missing_persistence_hours",
    ]


def _to_float(value: Any, default: float = 0.0) -> float:
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


def _to_int(value: Any, default: int = 0) -> int:
    return int(round(_to_float(value, default)))


def _to_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "y", "on"}:
            return True
        if lowered in {"0", "false", "no", "n", "off", ""}:
            return False
    return default


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _is_present(payload: Mapping[str, Any], key: str) -> bool:
    """A field is observed only when supplied with a real value.

    An explicitly supplied null/None is treated exactly like an absent field:
    it is never coerced into an observed False/0/0.0 behavioral signal.
    """
    return key in payload and payload.get(key) is not None


def extract_features(signals: Mapping[str, Any] | None = None) -> Dict[str, Any]:
    """Create deterministic features for the current behavioral/isolation signals.

    Missing telemetry is handled by safe defaults and explicit missing-signal flags.
    An explicitly supplied null/None value is treated exactly like an absent field
    and is never coerced into an observed False/0/0.0 signal.
    The output ordering is stable and matches the canonical feature schema.
    """
    payload = dict(signals or {})

    call_duration = _to_float(
        payload.get("call_duration_min", payload.get("call_duration_minutes", payload.get("duration_minutes"))),
        default=0.0,
    )
    if call_duration < 0:
        call_duration = 0.0

    is_unknown_number = _to_bool(payload.get("is_unknown_number"), default=False)
    is_video_call = _to_bool(payload.get("is_video_call"), default=False)

    hour_value = _to_int(payload.get("hour_of_day"), default=12)
    hour_value = max(0, min(23, hour_value))
    day_of_week = payload.get("day_of_week")
    if day_of_week is None and payload.get("is_weekend") is not None:
        weekend_value = _to_bool(payload.get("is_weekend"), default=False)
    elif day_of_week is not None:
        weekend_value = int(day_of_week in {5, 6})
    else:
        weekend_value = 0  # unknown - never fabricate weekend from hour_of_day

    caller_call_history = _to_int(payload.get("caller_call_history"), default=0)
    outgoing_activity_ratio = _to_float(payload.get("outgoing_activity_ratio"), default=0.5)
    outgoing_activity_ratio = _clamp(outgoing_activity_ratio, 0.0, 1.0)

    call_duration_log = math.log1p(call_duration) if call_duration >= 0 else 0.0
    is_early_morning = 1 if 5 <= hour_value <= 8 else 0
    is_late_night = 1 if hour_value >= 22 or hour_value <= 4 else 0

    if outgoing_activity_ratio < 0.33:
        activity_category = 0
    elif outgoing_activity_ratio < 0.66:
        activity_category = 1
    else:
        activity_category = 2

    screen_time_on_call_percent = _to_float(payload.get("screen_time_on_call_percent"), default=0.0)
    num_app_switches = _to_int(payload.get("num_app_switches"), default=0)
    num_home_presses = _to_int(payload.get("num_home_presses"), default=0)
    has_sms_activity = _to_bool(payload.get("has_sms_activity"), default=False)
    has_social_app_activity = _to_bool(payload.get("has_social_app_activity"), default=False)
    location_change = _to_float(payload.get("location_change"), default=0.0)
    screen_brightness = _to_float(payload.get("screen_brightness"), default=0.0)
    screen_on_continuous_hours = _to_float(payload.get("screen_on_continuous_hours"), default=0.0)
    persistence_hours = _to_float(payload.get("persistence_hours"), default=0.0)

    return {
        "call_duration_min": round(call_duration, 3),
        "is_unknown_number": 1 if is_unknown_number else 0,
        "is_video_call": 1 if is_video_call else 0,
        "hour_of_day": hour_value,
        "caller_call_history": caller_call_history,
        "outgoing_activity_ratio": round(outgoing_activity_ratio, 3),
        "is_weekend": int(weekend_value),
        "call_duration_log": round(call_duration_log, 3),
        "is_early_morning": int(is_early_morning),
        "is_late_night": int(is_late_night),
        "activity_category": int(activity_category),
        "screen_time_on_call_percent": round(screen_time_on_call_percent, 3),
        "num_app_switches": num_app_switches,
        "num_home_presses": num_home_presses,
        "has_sms_activity": 1 if has_sms_activity else 0,
        "has_social_app_activity": 1 if has_social_app_activity else 0,
        "location_change": round(location_change, 3),
        "screen_brightness": round(screen_brightness, 3),
        "screen_on_continuous_hours": round(screen_on_continuous_hours, 3),
        "persistence_hours": round(persistence_hours, 3),
        "is_missing_screen_time_on_call_percent": 0 if _is_present(payload, "screen_time_on_call_percent") else 1,
        "is_missing_num_app_switches": 0 if _is_present(payload, "num_app_switches") else 1,
        "is_missing_num_home_presses": 0 if _is_present(payload, "num_home_presses") else 1,
        "is_missing_has_sms_activity": 0 if _is_present(payload, "has_sms_activity") else 1,
        "is_missing_has_social_app_activity": 0 if _is_present(payload, "has_social_app_activity") else 1,
        "is_missing_location_change": 0 if _is_present(payload, "location_change") else 1,
        "is_missing_screen_brightness": 0 if _is_present(payload, "screen_brightness") else 1,
        "is_missing_screen_on_continuous_hours": 0 if _is_present(payload, "screen_on_continuous_hours") else 1,
        "is_missing_persistence_hours": 0 if _is_present(payload, "persistence_hours") else 1,
    }

