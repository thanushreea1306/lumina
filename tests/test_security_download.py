# tests/test_security_download.py
import os
import shutil

import pytest


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


TRAVERSAL_ATTEMPTS = [
    "..\\run.py",
    "..%5Crun.py",
    "..%2Frun.py",
    "..\\..\\README.md",
    "..%5C..%5CREADME.md",
    "..%2F..%2FREADME.md",
    "sub..\\run.py",
    "sub..%5Crun.py",
]


@pytest.mark.parametrize("filename", TRAVERSAL_ATTEMPTS)
def test_traversal_cannot_access_files_outside_reports(client, filename):
    """Any ../ or ..\\ traversal must be rejected, never serve repo files."""
    response = client.get(f"/api/download-report/{filename}")
    assert response.status_code == 404


def test_legitimate_report_download_still_works(client):
    """A real report generated into reports/ can still be downloaded."""
    from app.core.db import DB_PATH

    os.makedirs("reports", exist_ok=True)
    payload = {
        "call_duration_min": 120,
        "is_unknown_number": 1,
        "is_video_call": 1,
        "hour_of_day": 10,
        "caller_call_history": 0,
        "outgoing_activity_ratio": 0.1,
        "day_of_week": 2,
    }
    created = client.post("/api/generate-report", json=payload)
    assert created.status_code == 200
    pdf_path = created.json()["pdf_path"]
    assert os.path.exists(pdf_path)

    filename = os.path.basename(pdf_path)
    response = client.get(f"/api/download-report/{filename}")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content[:5] == b"%PDF-"

    try:
        os.remove(pdf_path)
    except OSError:
        pass
