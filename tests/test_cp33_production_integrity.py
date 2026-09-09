# tests/test_cp33_production_integrity.py
"""CP-33A Production Integrity Cleanup — key capability tests.

Covers the three production-integrity hardening items:
  A. Trusted-contact encryption at rest (Fernet, key env, fail-closed).
  B. Persistence-layer owner filtering for get_incident (SQLite/Postgres parity).
  C. Durable nonce replay protection backed by the persistence layer.
"""
from __future__ import annotations

import os
import uuid

import pytest

from app.evidence.auth import NonceTracker
from app.incident.crypto import (
    decrypt_contact_field,
    encrypt_contact_field,
    generate_encryption_key,
)
from app.incident.engine import IncidentEngine
from app.incident.models import Priority
from app.incident.store import IncidentStore
from app.incident.trusted_contact import (
    DeliveryChannel,
    TrustedContact,
    get_trusted_contact,
    save_trusted_contact,
)
from app.persistence.sqlite import SQLiteBackend

TEST_KEY_ENV = "LUMINA_ENCRYPTION_KEY"


# ---------------------------------------------------------------------------
# A. Encryption at rest
# ---------------------------------------------------------------------------


def _set_key() -> str:
    key = generate_encryption_key()
    os.environ[TEST_KEY_ENV] = key
    return key


class TestEncryptionAtRest:
    def test_ciphertext_is_not_plaintext(self):
        key = _set_key()
        enc = encrypt_contact_field("+919876543210")
        assert enc != "+919876543210"
        assert enc.startswith("gAAAA")  # Fernet v0 token header
        assert "+919876543210" not in enc

    def test_roundtrip(self):
        _set_key()
        assert decrypt_contact_field(encrypt_contact_field("+14155552671")) == "+14155552671"

    def test_legacy_plaintext_reads_back_unchanged(self):
        _set_key()
        # A pre-encryption row stores plaintext; we must keep it usable,
        # not crash or invent a token.
        assert decrypt_contact_field("+919876543210") == "+919876543210"

    def test_empty_fields_pass_through(self):
        _set_key()
        assert encrypt_contact_field("") == ""
        assert decrypt_contact_field("") == ""

    def test_encrypt_fail_closed_without_key(self, monkeypatch):
        monkeypatch.delenv(TEST_KEY_ENV, raising=False)
        with pytest.raises(RuntimeError):
            encrypt_contact_field("+919876543210")

    def test_decrypt_fail_closed_without_key_on_token(self, monkeypatch):
        key = generate_encryption_key()
        os.environ[TEST_KEY_ENV] = key
        token = encrypt_contact_field("+919876543210")
        monkeypatch.delenv(TEST_KEY_ENV, raising=False)
        with pytest.raises(RuntimeError):
            decrypt_contact_field(token)

    def test_backend_persists_encrypted_destination(self, tmp_path, monkeypatch):
        _set_key()
        db_path = str(tmp_path / "tc.db")
        monkeypatch.setenv("LUMINA_DB_PATH", db_path)
        backend = SQLiteBackend(path=db_path)
        contact = TrustedContact(
            owner_device_id="dev-enc-1",
            display_name="Mom",
            delivery_channel=DeliveryChannel.SMS,
            destination="+919876543210",
        )
        save_trusted_contact(contact)
        stored = backend.get_trusted_contact("dev-enc-1")
        assert stored["destination"] != "+919876543210"
        assert stored["destination"].startswith("gAAAA")

    def test_backend_reads_back_plaintext(self, tmp_path, monkeypatch):
        _set_key()
        db_path = str(tmp_path / "tc.db")
        monkeypatch.setenv("LUMINA_DB_PATH", db_path)
        SQLiteBackend(path=db_path)
        contact = TrustedContact(
            owner_device_id="dev-enc-2",
            display_name="Dad",
            delivery_channel=DeliveryChannel.SMS,
            destination="+14155552671",
        )
        save_trusted_contact(contact)
        got = get_trusted_contact("dev-enc-2")
        assert got is not None
        assert got.destination == "+14155552671"

    def test_legacy_plaintext_row_reads_back_safely(self, tmp_path, monkeypatch):
        _set_key()
        db_path = str(tmp_path / "tc.db")
        monkeypatch.setenv("LUMINA_DB_PATH", db_path)
        backend = SQLiteBackend(path=db_path)
        # Simulate a legacy row: plaintext destination already in the table.
        backend.save_trusted_contact(
            contact_id="legacy1",
            owner_device_id="dev-legacy",
            display_name="Mom",
            delivery_channel=DeliveryChannel.SMS.value,
            destination="+919876543210",
            enabled=True,
            automatic_help_enabled=False,
            configured_at="2024-01-01T00:00:00",
            updated_at="2024-01-01T00:00:00",
            created_at="2024-01-01T00:00:00",
        )
        got = get_trusted_contact("dev-legacy")
        assert got is not None
        assert got.destination == "+919876543210"


# ---------------------------------------------------------------------------
# B. Persistence-layer owner filtering
# ---------------------------------------------------------------------------


def _make_backend_with_incidents(tmp_path):
    store = IncidentStore(path=str(tmp_path / "owner.db"))
    engine = IncidentEngine(store=store)
    a = engine.create_incident(owner_device_id="owner-a")
    b = engine.create_incident(owner_device_id="owner-b")
    return store.backend, engine, a.incident_id, b.incident_id


class TestOwnerFiltering:
    def test_get_incident_unfiltered_returns_any(self, tmp_path):
        backend, engine, a_id, b_id = _make_backend_with_incidents(tmp_path)
        assert engine.get_incident(a_id).owner_device_id == "owner-a"
        assert engine.get_incident(b_id).owner_device_id == "owner-b"

    def test_get_incident_owner_filter_matches_owner(self, tmp_path):
        backend, engine, a_id, b_id = _make_backend_with_incidents(tmp_path)
        incident = engine.get_incident(a_id, owner_device_id="owner-a")
        assert incident is not None
        assert incident.incident_id == a_id

    def test_get_incident_owner_filter_hides_foreign(self, tmp_path):
        backend, engine, a_id, b_id = _make_backend_with_incidents(tmp_path)
        # A's incident is invisible to B at the persistence layer.
        assert engine.get_incident(a_id, owner_device_id="owner-b") is None
        assert backend.get_incident(a_id, owner_device_id="owner-b") is None

    def test_get_incident_owner_filter_missing_owner(self, tmp_path):
        backend, engine, a_id, b_id = _make_backend_with_incidents(tmp_path)
        assert engine.get_incident("does-not-exist", owner_device_id="owner-a") is None

    def test_get_incident_nonexistent_unfiltered(self, tmp_path):
        backend, engine, a_id, b_id = _make_backend_with_incidents(tmp_path)
        assert engine.get_incident("does-not-exist") is None

    def test_incident_priority_preserved_with_owner_filter(self, tmp_path):
        backend, engine, a_id, b_id = _make_backend_with_incidents(tmp_path)
        incident = engine.get_incident(a_id, owner_device_id="owner-a")
        assert incident.priority is not None


# ---------------------------------------------------------------------------
# C. Durable nonce replay protection
# ---------------------------------------------------------------------------


class TestDurableNonce:
    def test_nonce_persisted_and_replayed_after_tracker_restart(self, tmp_path):
        path = str(tmp_path / "nonce.db")
        backend = SQLiteBackend(path=path)
        device_id = uuid.uuid4().hex

        tracker1 = NonceTracker(persistence=backend)
        assert tracker1.is_replay(device_id, "nonce-1") is False

        # A fresh tracker with the same durable backend sees the nonce.
        tracker2 = NonceTracker(persistence=backend)
        assert tracker2.is_replay(device_id, "nonce-1") is True

    def test_distinct_nonces_are_not_replays(self, tmp_path):
        path = str(tmp_path / "nonce.db")
        backend = SQLiteBackend(path=path)
        tracker = NonceTracker(persistence=backend)
        device_id = uuid.uuid4().hex
        assert tracker.is_replay(device_id, "n1") is False
        assert tracker.is_replay(device_id, "n2") is False

    def test_in_memory_only_tracker_still_works(self):
        tracker = NonceTracker()
        device_id = uuid.uuid4().hex
        assert tracker.is_replay(device_id, "n1") is False
        assert tracker.is_replay(device_id, "n1") is True

    def test_prune_bounds_storage(self, tmp_path):
        path = str(tmp_path / "nonce.db")
        backend = SQLiteBackend(path=path)
        tracker = NonceTracker(persistence=backend)
        device_id = uuid.uuid4().hex
        tracker.is_replay(device_id, "prune-me")
        deleted = backend.prune_nonces(older_than="2999-01-01T00:00:00")
        assert deleted >= 1
        assert backend.is_nonce_used(device_id, "prune-me") is False