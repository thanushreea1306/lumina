# tests/test_evidence_framework.py
"""Unit tests for the evidence + decision foundation (pure logic, no API).

Covers: evidence creation, evidence status, provenance, missing-value
handling, temporal ordering, user observations, high-risk action
representation, decision-context construction, safety-state transitions,
explainability, and persistence/retrieval.
"""
import pytest

from app.evidence.actions import (
    HIGH_RISK_ACTIONS,
    HighRiskActionInstance,
    action_by_observation,
)
from app.evidence.db import EvidenceStore, make_session
from app.evidence.decision_context import build_decision_context
from app.evidence.explainability import build_decision
from app.evidence.ml_boundary import ml_status
from app.evidence.models import (
    ActionStatus,
    Evidence,
    EvidenceSource,
    EvidenceStatus,
    SafetyState,
    Session,
    TimelineEventType,
    UserObservation,
    UserObservationType,
)
from app.evidence.safety_state import evaluate_state, state_spec


def make_evidence(
    session_id="s1",
    obs_type=UserObservationType.OTP_REQUEST,
    seq=0,
):
    return UserObservation(
        observation_type=obs_type,
        session_id=session_id,
        timestamp="2026-09-02T10:00:00",
        sequence=seq,
    ).to_evidence()


# ---- 1. evidence creation ----
def test_evidence_is_retrievable_and_typed():
    ev = make_evidence()
    assert isinstance(ev, Evidence)
    assert ev.type == "OTP_REQUEST"
    assert ev.evidence_id
    assert ev.session_id == "s1"


# ---- 2. evidence status ----
def test_user_observation_is_user_confirmed():
    ev = make_evidence()
    assert ev.status == EvidenceStatus.USER_CONFIRMED
    assert ev.source == EvidenceSource.USER


def test_device_evidence_can_hold_observed_status():
    ev = Evidence(
        session_id="s1",
        type="call_duration_seconds",
        value=120,
        status=EvidenceStatus.OBSERVED,
        source=EvidenceSource.DEVICE,
        timestamp="2026-09-02T10:00:00",
        sequence=0,
    )
    assert ev.status == EvidenceStatus.OBSERVED
    assert ev.source == EvidenceSource.DEVICE


# ---- 3. provenance ----
def test_evidence_provenance_is_preserved_in_dict():
    d = make_evidence().to_dict()
    assert d["source"] == "USER"
    assert d["status"] == "USER_CONFIRMED"
    assert d["confidence"] is None


# ---- 4. missing-value handling ----
def test_missing_value_cannot_be_marked_observed():
    with pytest.raises(ValueError):
        Evidence(
            session_id="s1", type="caller_number", value=None,
            status=EvidenceStatus.OBSERVED, source=EvidenceSource.DEVICE,
            timestamp="t", sequence=0,
        )


def test_missing_value_repr_via_status():
    ev = Evidence(
        session_id="s1", type="caller_number", value=None,
        status=EvidenceStatus.UNKNOWN, source=EvidenceSource.DEVICE,
        timestamp="t", sequence=0,
    )
    assert ev.status == EvidenceStatus.UNKNOWN
    assert ev.value is None


def test_no_fabricated_confidence():
    ev = make_evidence()
    assert ev.confidence is None


def test_confidence_range_is_enforced():
    with pytest.raises(ValueError):
        Evidence(
            session_id="s1", type="x", value=1,
            status=EvidenceStatus.INFERRED, source=EvidenceSource.MODEL,
            timestamp="t", sequence=0, confidence=1.5,
        )


# ---- 5. user observations ----
def test_all_observation_categories_are_definable():
    names = [o.name for o in UserObservationType]
    assert "AUTHORITY_CLAIM" in names
    assert "THREAT_OF_ARREST" in names
    assert "OTP_REQUEST" in names
    assert "GIFT_CARD_REQUEST" in names
    assert len(names) >= 16


def test_user_observation_is_not_an_automatic_truth():
    """An observation only becomes evidence via USER_CONFIRMED; the not* statuses exist."""
    assert EvidenceStatus.UNKNOWN != EvidenceStatus.USER_CONFIRMED


# ---- 6. high-risk action representation ----
def test_high_risk_actions_registry_is_complete():
    names = {a.action.value for a in HIGH_RISK_ACTIONS.values()}
    for expected in ("SEND_MONEY", "SHARE_OTP", "SHARE_PASSWORD", "SHARE_CREDENTIAL",
                     "SHARE_ID_DOCUMENT", "INSTALL_REMOTE_ACCESS", "GRANT_REMOTE_CONTROL",
                     "TRANSFER_CRYPTO", "SHARE_BANK_DETAILS"):
        assert expected in names


def test_high_risk_action_has_required_attributes():
    a = HIGH_RISK_ACTIONS["SHARE_OTP"]
    assert a.reversibility.value == "IRREVERSIBLE"
    assert a.verifiable_independently is False
    assert a.trusted_person_intervention_helps is True


def test_action_by_observation_maps_requests():
    related = action_by_observation(UserObservationType.CRYPTO_REQUEST)
    assert any(x.action.value == "TRANSFER_CRYPTO" for x in related)


def test_high_risk_action_instance_status():
    inst = HighRiskActionInstance(
        action=list(HIGH_RISK_ACTIONS)[0], status=ActionStatus.REQUESTED,
        session_id="s1", timestamp="t", sequence=1,
    )
    assert inst.status == ActionStatus.REQUESTED


# ---- 7. decision context ----
def test_empty_session_context_is_clear_and_uncertain():
    session = Session(session_id="s1", started_at="t0")
    ctx = build_decision_context(session)
    assert ctx.observations == []
    assert ctx.duration_seconds is None
    assert "caller_identity unavailable" in ctx.missing_information


def test_context_reflects_observation_and_requested_action():
    session = Session(session_id="s1", started_at="t0")
    session.add_evidence(make_evidence(seq=0))
    ctx = build_decision_context(session)
    assert UserObservationType.OTP_REQUEST in ctx.observations
    assert any(a.action.value == "SHARE_OTP" for a in ctx.high_risk_actions)


def test_open_session_context_duration_unknown():
    session = Session(session_id="s1", started_at="t0")
    session.add_event(TimelineEventType.CALL_STARTED, "2026-09-02T10:00:00")
    ctx = build_decision_context(session)
    assert ctx.call_started is True
    assert ctx.duration_seconds is None


def test_context_duration_from_start_and_end():
    session = Session(session_id="s1", started_at="t0")
    session.add_event(TimelineEventType.CALL_STARTED, "2026-09-02T10:00:00")
    session.add_event(TimelineEventType.CALL_ENDED, "2026-09-02T10:05:30")
    ctx = build_decision_context(session)
    assert ctx.duration_seconds == 330


# ---- 8. temporal ordering ----
def test_timeline_orders_by_sequence():
    session = Session(session_id="s1", started_at="t0")
    session.add_event(TimelineEventType.CALL_ENDED, "t3")
    session.add_event(TimelineEventType.CALL_STARTED, "t1")
    session.add_event(TimelineEventType.CALL_ACTIVE, "t2")
    ordered = [e.event_type.value for e in session.ordered_events()]
    assert ordered == ["CALL_ENDED", "CALL_STARTED", "CALL_ACTIVE"]
    assert [e.sequence for e in session.ordered_events()] == [0, 1, 2]


# ---- 9. safety-state transitions ----
def test_clear_when_no_evidence():
    ctx = build_decision_context(Session(session_id="s1", started_at="t"))
    assert evaluate_state(ctx) == SafetyState.CLEAR


def test_watch_with_observation_no_action():
    session = Session(session_id="s1", started_at="t")
    session.add_evidence(make_evidence(obs_type=UserObservationType.URGENCY, seq=0))
    ctx = build_decision_context(session)
    assert evaluate_state(ctx) == SafetyState.WATCH


def test_pause_on_high_value_action():
    session = Session(session_id="s1", started_at="t")
    session.add_evidence(make_evidence(obs_type=UserObservationType.OTP_REQUEST, seq=0))
    ctx = build_decision_context(session)
    assert evaluate_state(ctx) == SafetyState.PAUSE


def test_verify_on_regular_requested_action():
    session = Session(session_id="s1", started_at="t")
    session.add_evidence(make_evidence(obs_type=UserObservationType.MONEY_REQUEST, seq=0))
    ctx = build_decision_context(session)
    assert evaluate_state(ctx) == SafetyState.VERIFY


def test_protect_on_coercion_plus_high_value():
    session = Session(session_id="s1", started_at="t")
    session.add_evidence(make_evidence(obs_type=UserObservationType.AUTHORITY_CLAIM, seq=0))
    session.add_evidence(make_evidence(obs_type=UserObservationType.THREAT_OF_ARREST, seq=1))
    session.add_evidence(make_evidence(obs_type=UserObservationType.OTP_REQUEST, seq=2))
    ctx = build_decision_context(session)
    assert evaluate_state(ctx) == SafetyState.PROTECT


def test_recovery_when_action_performed():
    session = Session(session_id="s1", started_at="t")
    session.add_evidence(make_evidence(obs_type=UserObservationType.OTP_REQUEST, seq=0))
    session.add_evidence(Evidence(
        session_id="s1", type="user_response", value=True,
        status=EvidenceStatus.USER_CONFIRMED, source=EvidenceSource.USER,
        timestamp="t2", sequence=1, metadata={"action": "SHARE_OTP", "response": "performed"},
    ))
    ctx = build_decision_context(session)
    assert evaluate_state(ctx) == SafetyState.RECOVERY


def test_state_specs_are_complete():
    for state in SafetyState:
        spec = state_spec(state)
        assert spec["recommended_user_action"]


def test_states_do_not_use_numeric_scores():
    for state in SafetyState:
        for value in state_spec(state).values():
            assert not isinstance(value, (int, float))


# ---- 10. explainability ----
def test_decision_is_explainable_and_score_free():
    session = Session(session_id="s1", started_at="t")
    session.add_evidence(make_evidence(obs_type=UserObservationType.AUTHORITY_CLAIM, seq=0))
    session.add_evidence(make_evidence(obs_type=UserObservationType.OTP_REQUEST, seq=1))
    ctx = build_decision_context(session)
    state = evaluate_state(ctx)
    decision = build_decision(ctx, state)
    d = decision.to_dict()
    assert d["state"] == "PROTECT"
    assert d["reason_codes"]
    assert d["recommended_action"]
    assert "caller_identity unavailable" in d["missing_information"]
    assert "uncertainty" in d
    # No fake values: no confidence / risk_score fields.
    assert "confidence" not in d
    assert "risk_score" not in d


def test_uncertainty_comes_from_missing_information_only():
    session = Session(session_id="s1", started_at="t")
    session.add_evidence(make_evidence(seq=0))
    ctx = build_decision_context(session)
    decision = build_decision(ctx, evaluate_state(ctx))
    assert set(decision.uncertainty) == set(decision.missing_information)


# ---- 11. persistence / retrieval ----
def test_store_roundtrip(tmp_path):
    store = EvidenceStore(path=str(tmp_path / "evidence_test.db"))
    session = make_session()
    store.create_session(session.session_id, session.started_at)
    event = session.add_event(TimelineEventType.CALL_STARTED, "2026-09-02T10:00:00")
    store.append_event(event)
    evidence = make_evidence(session_id=session.session_id, seq=1)
    store.add_evidence(evidence)

    got = store.get_session(session.session_id)
    assert got is not None
    assert len(got.events) == 1
    assert got.events[0].event_type == TimelineEventType.CALL_STARTED
    assert len(got.evidence) == 1
    assert got.evidence[0].type == "OTP_REQUEST"


def test_store_preserves_unknown_value(tmp_path):
    store = EvidenceStore(path=str(tmp_path / "evidence_test2.db"))
    session = make_session()
    store.create_session(session.session_id, session.started_at)
    ev = Evidence(
        session_id=session.session_id, type="caller_number", value=None,
        status=EvidenceStatus.UNKNOWN, source=EvidenceSource.DEVICE,
        timestamp="t", sequence=0,
    )
    store.add_evidence(ev)
    got = store.get_session(session.session_id)
    assert got.evidence[0].status == EvidenceStatus.UNKNOWN
    assert got.evidence[0].value is None


def test_store_records_and_reads_decision(tmp_path):
    store = EvidenceStore(path=str(tmp_path / "evidence_test3.db"))
    session = make_session()
    store.create_session(session.session_id, session.started_at)
    store.record_decision(session.session_id, {"state": "CLEAR", "reason_codes": [], "recommended_action": "none"})
    d = store.get_latest_decision(session.session_id)
    assert d is not None
    assert d["state"] == "CLEAR"


def test_store_records_outcome(tmp_path):
    store = EvidenceStore(path=str(tmp_path / "evidence_test4.db"))
    session = make_session()
    store.create_session(session.session_id, session.started_at)
    store.record_outcome(session.session_id, "reported")
    assert store.get_outcomes(session.session_id) == ["reported"]


def test_store_append_only_timeline_sequence(tmp_path):
    store = EvidenceStore(path=str(tmp_path / "evidence_test5.db"))
    session = make_session()
    store.create_session(session.session_id, session.started_at)
    for i, t in enumerate(("t1", "t2", "t3")):
        store.append_event(session.add_event(TimelineEventType.CALL_ACTIVE, t))
    got = store.get_session(session.session_id)
    assert [e.sequence for e in got.events] == [0, 1, 2]


# ---- 12. ml boundary ----
def test_ml_boundary_reports_not_implemented_honestly():
    status = ml_status()
    assert status["status"] == "not_implemented"
    assert status["real_labeled_data_available"] is False
    assert "advisory" in status["role"]