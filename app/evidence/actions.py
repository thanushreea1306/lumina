# app/evidence/actions.py
"""High-risk action model: potentially irreversible actions and their metadata.

Principle: the closer the user is to an irreversible harmful action, the
stronger the safety intervention should be. Each action carries the attributes
needed to rank that closeness truthfully — not a fabricated score.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

from app.evidence.models import (
    ActionStatus,
    UserObservationType,
)


class Irreversibility(str, Enum):
    IRREVERSIBLE = "IRREVERSIBLE"      # cannot be undone
    HARD_TO_REVERSE = "HARD_TO_REVERSE"
    REVERSIBLE = "REVERSIBLE"


class Impact(str, Enum):
    FINANCIAL = "FINANCIAL"
    SECURITY = "SECURITY"
    IDENTITY = "IDENTITY"
    ACCESS = "ACCESS"


class Urgency(str, Enum):
    IMMEDIATE = "IMMEDIATE"
    HIGH = "HIGH"
    MODERATE = "MODERATE"


class HighRiskActionType(str, Enum):
    SEND_MONEY = "SEND_MONEY"
    SHARE_OTP = "SHARE_OTP"
    SHARE_PASSWORD = "SHARE_PASSWORD"
    SHARE_CREDENTIAL = "SHARE_CREDENTIAL"
    SHARE_ID_DOCUMENT = "SHARE_ID_DOCUMENT"
    INSTALL_REMOTE_ACCESS = "INSTALL_REMOTE_ACCESS"
    GRANT_REMOTE_CONTROL = "GRANT_REMOTE_CONTROL"
    TRANSFER_CRYPTO = "TRANSFER_CRYPTO"
    SHARE_BANK_DETAILS = "SHARE_BANK_DETAILS"


@dataclass(frozen=True)
class HighRiskAction:
    """Static attributes of a high-risk action (single source of truth)."""
    action: HighRiskActionType
    reversibility: Irreversibility
    impact: List[Impact]
    urgency: Urgency
    verifiable_independently: bool
    trusted_person_intervention_helps: bool
    description: str

    # Which user-observable request(s) typically precede this action.
    related_observation_types: List[UserObservationType] = ()

    def to_dict(self) -> dict:
        return {
            "action": self.action.value,
            "reversibility": self.reversibility.value,
            "impact": [i.value for i in self.impact],
            "urgency": self.urgency.value,
            "verifiable_independently": self.verifiable_independently,
            "trusted_person_intervention_helps": self.trusted_person_intervention_helps,
            "description": self.description,
            "related_observation_types": [o.value for o in self.related_observation_types],
        }


HIGH_RISK_ACTIONS: dict[HighRiskActionType, HighRiskAction] = {
    HighRiskActionType.SEND_MONEY: HighRiskAction(
        action=HighRiskActionType.SEND_MONEY,
        reversibility=Irreversibility.HARD_TO_REVERSE,
        impact=[Impact.FINANCIAL],
        urgency=Urgency.HIGH,
        verifiable_independently=True,
        trusted_person_intervention_helps=True,
        description="Sending money to the caller.",
        related_observation_types=[UserObservationType.MONEY_REQUEST,
                                   UserObservationType.BANK_TRANSFER_REQUEST],
    ),
    HighRiskActionType.SHARE_OTP: HighRiskAction(
        action=HighRiskActionType.SHARE_OTP,
        reversibility=Irreversibility.IRREVERSIBLE,
        impact=[Impact.SECURITY],
        urgency=Urgency.IMMEDIATE,
        verifiable_independently=False,
        trusted_person_intervention_helps=True,
        description="Sharing a one-time password / code with the caller.",
        related_observation_types=[UserObservationType.OTP_REQUEST],
    ),
    HighRiskActionType.SHARE_PASSWORD: HighRiskAction(
        action=HighRiskActionType.SHARE_PASSWORD,
        reversibility=Irreversibility.IRREVERSIBLE,
        impact=[Impact.SECURITY, Impact.IDENTITY],
        urgency=Urgency.IMMEDIATE,
        verifiable_independently=False,
        trusted_person_intervention_helps=True,
        description="Sharing an account password.",
        related_observation_types=[UserObservationType.PASSWORD_REQUEST],
    ),
    HighRiskActionType.SHARE_CREDENTIAL: HighRiskAction(
        action=HighRiskActionType.SHARE_CREDENTIAL,
        reversibility=Irreversibility.IRREVERSIBLE,
        impact=[Impact.SECURITY, Impact.IDENTITY],
        urgency=Urgency.IMMEDIATE,
        verifiable_independently=False,
        trusted_person_intervention_helps=True,
        description="Sharing login credentials / keys.",
        related_observation_types=[UserObservationType.PASSWORD_REQUEST],
    ),
    HighRiskActionType.SHARE_ID_DOCUMENT: HighRiskAction(
        action=HighRiskActionType.SHARE_ID_DOCUMENT,
        reversibility=Irreversibility.HARD_TO_REVERSE,
        impact=[Impact.IDENTITY],
        urgency=Urgency.IMMEDIATE,
        verifiable_independently=False,
        trusted_person_intervention_helps=True,
        description="Sharing a copy of an identity document.",
        related_observation_types=[UserObservationType.IDENTITY_DOCUMENT_REQUEST],
    ),
    HighRiskActionType.INSTALL_REMOTE_ACCESS: HighRiskAction(
        action=HighRiskActionType.INSTALL_REMOTE_ACCESS,
        reversibility=Irreversibility.REVERSIBLE,
        impact=[Impact.ACCESS, Impact.SECURITY],
        urgency=Urgency.HIGH,
        verifiable_independently=True,
        trusted_person_intervention_helps=True,
        description="Installing an app that grants remote access to this device.",
        related_observation_types=[UserObservationType.APP_INSTALL_REQUEST,
                                   UserObservationType.REMOTE_ACCESS_REQUEST],
    ),
    HighRiskActionType.GRANT_REMOTE_CONTROL: HighRiskAction(
        action=HighRiskActionType.GRANT_REMOTE_CONTROL,
        reversibility=Irreversibility.HARD_TO_REVERSE,
        impact=[Impact.ACCESS, Impact.SECURITY, Impact.IDENTITY],
        urgency=Urgency.HIGH,
        verifiable_independently=True,
        trusted_person_intervention_helps=True,
        description="Granting the caller remote control of this device.",
        related_observation_types=[UserObservationType.REMOTE_ACCESS_REQUEST],
    ),
    HighRiskActionType.TRANSFER_CRYPTO: HighRiskAction(
        action=HighRiskActionType.TRANSFER_CRYPTO,
        reversibility=Irreversibility.IRREVERSIBLE,
        impact=[Impact.FINANCIAL],
        urgency=Urgency.IMMEDIATE,
        verifiable_independently=True,
        trusted_person_intervention_helps=True,
        description="Transferring cryptocurrency to the caller.",
        related_observation_types=[UserObservationType.CRYPTO_REQUEST],
    ),
    HighRiskActionType.SHARE_BANK_DETAILS: HighRiskAction(
        action=HighRiskActionType.SHARE_BANK_DETAILS,
        reversibility=Irreversibility.HARD_TO_REVERSE,
        impact=[Impact.FINANCIAL, Impact.IDENTITY],
        urgency=Urgency.HIGH,
        verifiable_independently=False,
        trusted_person_intervention_helps=True,
        description="Sharing bank account details with the caller.",
        related_observation_types=[UserObservationType.BANK_TRANSFER_REQUEST,
                                   UserObservationType.MONEY_REQUEST],
    ),
}


def action_by_observation(obs_type: UserObservationType) -> List[HighRiskAction]:
    """Return the high-risk actions that can follow a given user observation."""
    return [
        a for a in HIGH_RISK_ACTIONS.values()
        if obs_type in a.related_observation_types
    ]


@dataclass
class HighRiskActionInstance:
    """A high-risk action scoped to a session, with its current status."""
    action: HighRiskActionType
    status: ActionStatus
    session_id: str
    timestamp: str
    sequence: int

    def to_dict(self) -> dict:
        base = HIGH_RISK_ACTIONS[self.action].to_dict()
        base["status"] = self.status.value
        base["session_id"] = self.session_id
        base["timestamp"] = self.timestamp
        base["sequence"] = self.sequence
        return base
