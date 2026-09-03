# app/incident/evidence_map.py
"""Evidence-to-incident mapping rules.

Maps observation types (from the existing evidence model) to:
  - Exposure categories that may be affected
  - User action types that may have been performed
  - Epistemic status of conclusions

Rules are deterministic and conservative:
  - A REQUEST never automatically becomes a CONFIRMED action
  - Exposure escalates only with explicit evidence
  - Unknowns remain unknown until evidence arrives
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from app.evidence.models import UserObservationType
from app.incident.models import (
    ExposureCategory,
    ExposureLevel,
    ExposureState,
    UserActionType,
)


@dataclass(frozen=True)
class ExposureMapping:
    """How a single observation type affects exposure."""
    category: ExposureCategory
    request_level: ExposureLevel  # level when request is observed
    confirmed_level: ExposureLevel  # level when user confirms action
    request_description: str  # what the request implies
    confirmed_description: str  # what confirmed action implies


@dataclass(frozen=True)
class ActionMapping:
    """Maps a request observation to a potential user action."""
    action_type: UserActionType
    description: str


# ---- Observation → Exposure mappings ----
# These are conservative: a request is POTENTIALLY_EXPOSED, not USER_CONFIRMED_EXPOSED.

_OBSERVATION_EXPOSURE_MAP: Dict[UserObservationType, List[ExposureMapping]] = {
    UserObservationType.MONEY_REQUEST: [
        ExposureMapping(
            category=ExposureCategory.MONEY,
            request_level=ExposureLevel.POTENTIALLY_EXPOSED,
            confirmed_level=ExposureLevel.USER_CONFIRMED_EXPOSED,
            request_description="Money was requested",
            confirmed_description="User confirmed money was sent",
        ),
    ],
    UserObservationType.BANK_TRANSFER_REQUEST: [
        ExposureMapping(
            category=ExposureCategory.MONEY,
            request_level=ExposureLevel.POTENTIALLY_EXPOSED,
            confirmed_level=ExposureLevel.USER_CONFIRMED_EXPOSED,
            request_description="Bank transfer was requested",
            confirmed_description="User confirmed bank transfer was made",
        ),
        ExposureMapping(
            category=ExposureCategory.ACCOUNT,
            request_level=ExposureLevel.POTENTIALLY_EXPOSED,
            confirmed_level=ExposureLevel.USER_CONFIRMED_EXPOSED,
            request_description="Bank transfer may expose account details",
            confirmed_description="Bank account details were shared",
        ),
    ],
    UserObservationType.OTP_REQUEST: [
        ExposureMapping(
            category=ExposureCategory.AUTHENTICATION,
            request_level=ExposureLevel.POTENTIALLY_EXPOSED,
            confirmed_level=ExposureLevel.USER_CONFIRMED_EXPOSED,
            request_description="OTP/code was requested",
            confirmed_description="User confirmed OTP was shared",
        ),
    ],
    UserObservationType.PASSWORD_REQUEST: [
        ExposureMapping(
            category=ExposureCategory.AUTHENTICATION,
            request_level=ExposureLevel.POTENTIALLY_EXPOSED,
            confirmed_level=ExposureLevel.USER_CONFIRMED_EXPOSED,
            request_description="Password was requested",
            confirmed_description="User confirmed password was shared",
        ),
    ],
    UserObservationType.IDENTITY_DOCUMENT_REQUEST: [
        ExposureMapping(
            category=ExposureCategory.IDENTITY,
            request_level=ExposureLevel.POTENTIALLY_EXPOSED,
            confirmed_level=ExposureLevel.USER_CONFIRMED_EXPOSED,
            request_description="Identity document was requested",
            confirmed_description="User confirmed identity document was shared",
        ),
    ],
    UserObservationType.REMOTE_ACCESS_REQUEST: [
        ExposureMapping(
            category=ExposureCategory.DEVICE,
            request_level=ExposureLevel.POTENTIALLY_EXPOSED,
            confirmed_level=ExposureLevel.USER_CONFIRMED_EXPOSED,
            request_description="Remote access was requested",
            confirmed_description="User confirmed remote access was granted",
        ),
    ],
    UserObservationType.APP_INSTALL_REQUEST: [
        ExposureMapping(
            category=ExposureCategory.DEVICE,
            request_level=ExposureLevel.POTENTIALLY_EXPOSED,
            confirmed_level=ExposureLevel.USER_CONFIRMED_EXPOSED,
            request_description="App installation was requested",
            confirmed_description="User confirmed app was installed",
        ),
    ],
    UserObservationType.CRYPTO_REQUEST: [
        ExposureMapping(
            category=ExposureCategory.MONEY,
            request_level=ExposureLevel.POTENTIALLY_EXPOSED,
            confirmed_level=ExposureLevel.USER_CONFIRMED_EXPOSED,
            request_description="Cryptocurrency transfer was requested",
            confirmed_description="User confirmed cryptocurrency was transferred",
        ),
    ],
    UserObservationType.GIFT_CARD_REQUEST: [
        ExposureMapping(
            category=ExposureCategory.MONEY,
            request_level=ExposureLevel.POTENTIALLY_EXPOSED,
            confirmed_level=ExposureLevel.USER_CONFIRMED_EXPOSED,
            request_description="Gift card purchase was requested",
            confirmed_description="User confirmed gift cards were purchased",
        ),
    ],
    # These observations don't directly map to exposure categories
    # but affect state calculation
    UserObservationType.AUTHORITY_CLAIM: [],
    UserObservationType.THREAT_OF_ARREST: [],
    UserObservationType.THREAT_OF_LEGAL_ACTION: [],
    UserObservationType.URGENCY: [],
    UserObservationType.SECRECY_REQUEST: [],
    UserObservationType.INDEPENDENT_VERIFICATION_BLOCKED: [],
    UserObservationType.CALL_BACK_INSTRUCTION: [],
}


# ---- Observation → Potential User Action mappings ----
# These map what the REQUEST implies the user MIGHT have done.

_OBSERVATION_ACTION_MAP: Dict[UserObservationType, ActionMapping] = {
    UserObservationType.OTP_REQUEST: ActionMapping(
        action_type=UserActionType.SHARED_OTP,
        description="Shared OTP/code",
    ),
    UserObservationType.PASSWORD_REQUEST: ActionMapping(
        action_type=UserActionType.SHARED_PASSWORD,
        description="Shared password",
    ),
    UserObservationType.MONEY_REQUEST: ActionMapping(
        action_type=UserActionType.SENT_MONEY,
        description="Sent money",
    ),
    UserObservationType.BANK_TRANSFER_REQUEST: ActionMapping(
        action_type=UserActionType.SENT_MONEY,
        description="Made bank transfer",
    ),
    UserObservationType.CRYPTO_REQUEST: ActionMapping(
        action_type=UserActionType.SENT_MONEY,
        description="Transferred cryptocurrency",
    ),
    UserObservationType.GIFT_CARD_REQUEST: ActionMapping(
        action_type=UserActionType.SENT_MONEY,
        description="Purchased gift cards",
    ),
    UserObservationType.IDENTITY_DOCUMENT_REQUEST: ActionMapping(
        action_type=UserActionType.SHARED_DOCUMENT,
        description="Shared identity document",
    ),
    UserObservationType.REMOTE_ACCESS_REQUEST: ActionMapping(
        action_type=UserActionType.GRANTED_REMOTE_ACCESS,
        description="Granted remote access",
    ),
    UserObservationType.APP_INSTALL_REQUEST: ActionMapping(
        action_type=UserActionType.INSTALLED_APPLICATION,
        description="Installed application",
    ),
}


def get_exposure_mappings(observation_type: UserObservationType) -> List[ExposureMapping]:
    """Get exposure mappings for an observation type."""
    return _OBSERVATION_EXPOSURE_MAP.get(observation_type, [])


def get_action_mapping(observation_type: UserObservationType) -> Optional[ActionMapping]:
    """Get the potential user action mapping for an observation type."""
    return _OBSERVATION_ACTION_MAP.get(observation_type)


def get_all_affected_categories(
    observation_types: Set[UserObservationType],
) -> Dict[ExposureCategory, ExposureLevel]:
    """Compute the highest exposure level per category from a set of observations."""
    result: Dict[ExposureCategory, ExposureLevel] = {}
    level_priority = {
        ExposureLevel.NOT_INDICATED: 0,
        ExposureLevel.UNKNOWN: 1,
        ExposureLevel.POTENTIALLY_EXPOSED: 2,
        ExposureLevel.USER_CONFIRMED_EXPOSED: 3,
    }
    for obs_type in observation_types:
        for mapping in get_exposure_mappings(obs_type):
            current = result.get(mapping.category, ExposureLevel.NOT_INDICATED)
            if level_priority.get(mapping.request_level, 0) > level_priority.get(current, 0):
                result[mapping.category] = mapping.request_level
    return result
