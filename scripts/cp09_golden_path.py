"""CP-09 PHASE H: Live golden-path walk of the real incident stack.

Drives the REAL FastAPI app (TestClient -> app.main.app) against isolated temp
databases, walking the full incident lifecycle end-to-end:

  1. Register a device and create an incident
  2. Add an evidence observation
  3. Add a transcript (with a stable batch_id) -> evidence extracted + claim
  4. Re-submit the SAME batch_id -> deduplicated (no double evidence)
  5. Confirm a user action -> exposure escalates to USER_CONFIRMED_EXPOSED
  6. Close the incident -> status CLOSED, timeline INCIDENT_CLOSED
  7. Verify a closed incident stays CLOSED after further mutations
  8. Verify a foreign device still cannot access the incident (403)
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

from app.evidence import router as evidence_router
from app.evidence.auth import NonceTracker, generate_device_credentials
from app.evidence.db import EvidenceStore
from app.incident import router as incident_router
from app.incident.engine import IncidentEngine
from app.incident.store import IncidentStore
from app.main import app
from tests.conftest import AuthClient


def run_golden_path():
    tmp = Path(tempfile.mkdtemp(prefix="lumina_golden_"))
    print(f"[golden] temp db dir: {tmp}")

    # Point the real routers at the SAME real store + isolated DB files.
    incident_router._engine = IncidentEngine(
        IncidentStore(str(tmp / "incident.db"))
    )
    incident_router._store = EvidenceStore(
        path=str(tmp / "auth.db")
    )
    evidence_router._nonce_tracker = NonceTracker()

    # Also point the evidence router's store to the same auth DB if it exists.
    from app.evidence.db import EvidenceStore as EStore
    evidence_router._store = EStore(path=str(tmp / "auth.db"))

    client = TestClient(app)

    da_id, da_secret = generate_device_credentials()
    db_id, db_secret = generate_device_credentials()
    incident_router._store.register_device(da_id, da_secret)
    incident_router._store.register_device(db_id, db_secret)
    a = AuthClient(client, da_id, da_secret)
    b = AuthClient(client, db_id, db_secret)

    checks = []

    def ok(name, cond, detail=""):
        checks.append((name, bool(cond), detail))
        print(f"  [{'PASS' if cond else 'FAIL'}] {name} {detail}")

    # 1. Create incident
    r = a.post("/api/incidents", json={})
    assert r.status_code == 200, r.text
    inc_id = r.json()["incident_id"]
    ok("create incident", r.json()["status"] in ("ACTIVE", "MONITORING", "ACTION_REQUIRED"),
       f"id={inc_id} status={r.json()['status']}")

    # 2. Add an evidence observation
    r = a.post(f"/api/incidents/{inc_id}/evidence", json={"observation_type": "OTP_REQUEST"})
    ok("add evidence observation", r.status_code == 200, f"status={r.status_code}")

    # 3. Add transcript with a stable batch_id
    r = a.post(f"/api/incidents/{inc_id}/transcript",
               json={"text": "This is a bank representative, give me your OTP right now",
                     "batch_id": "golden-batch-1"})
    assert r.status_code == 200, r.text
    body = r.json()
    ok("transcript extracts evidence", body["observations_extracted"] > 0,
       f"obs={body['observations_extracted']}")

    # 4. Re-submit the same batch_id -> deduplicated
    r1 = a.get(f"/api/incidents/{inc_id}").json()
    tl_before = len(r1["timeline"])
    r = a.post(f"/api/incidents/{inc_id}/transcript",
               json={"text": "This is a bank representative, give me your OTP right now",
                     "batch_id": "golden-batch-1"})
    r2 = a.get(f"/api/incidents/{inc_id}").json()
    ok("same batch_id deduplicated", len(r2["timeline"]) == tl_before,
       f"timeline {tl_before}->{len(r2['timeline'])}")

    # 5. Confirm a user action
    r = a.post(f"/api/incidents/{inc_id}/actions",
               json={"action_type": "SHARED_OTP", "description": "I shared the OTP"})
    ok("confirm action", r.status_code == 200, f"status={r.status_code}")
    exp = a.get(f"/api/incidents/{inc_id}").json()["exposure"]
    auth_level = exp.get("AUTHENTICATION", {}).get("level")
    ok("exposure escalates on confirmation",
       auth_level == "USER_CONFIRMED_EXPOSED", f"auth={auth_level}")

    # 6. Close the incident
    r = a.post(f"/api/incidents/{inc_id}/close", json={"reason": "resolved"})
    ok("close incident", r.status_code == 200 and r.json()["status"] == "CLOSED",
       f"status={r.json().get('status')}")
    fetched = a.get(f"/api/incidents/{inc_id}").json()
    tl_types = [e["entry_type"] for e in fetched["timeline"]]
    ok("INCIDENT_CLOSED in timeline", "INCIDENT_CLOSED" in tl_types)

    # Timeline label appears (frontend label source of truth already tested).
    ok("closed incident retains evidence", len(fetched["timeline"]) >= 3,
       f"timeline={len(fetched['timeline'])}")

    # 7. Closed stays closed after further mutations
    a.post(f"/api/incidents/{inc_id}/evidence", json={"observation_type": "THREAT_OF_ARREST"})
    after = a.get(f"/api/incidents/{inc_id}").json()
    ok("closed stays closed after mutation", after["status"] == "CLOSED",
       f"status={after['status']}")

    # 8. Foreign device cannot access
    r = b.get(f"/api/incidents/{inc_id}")
    ok("foreign device 403", r.status_code == 403, f"status={r.status_code}")
    r = b.post(f"/api/incidents/{inc_id}/close", json={})
    ok("foreign close 403", r.status_code == 403, f"status={r.status_code}")

    # ---- Summary ----
    passed = sum(1 for _, c, _ in checks if c)
    failed = sum(1 for _, c, _ in checks if not c)
    print(f"\n[golden] {passed} passed, {failed} failed")
    if failed:
        for name, c, d in checks:
            if not c:
                print(f"  FAILED: {name} {d}")
        raise SystemExit(1)
    print("[golden] GOLDEN PATH OK")


if __name__ == "__main__":
    run_golden_path()
