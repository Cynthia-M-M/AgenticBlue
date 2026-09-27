"""
Tests for the demo appointments endpoint.

Demonstrates:
  - Happy path (correct payload → 200)
  - Frontend drift bug (wrong field name → 422)
"""
import pytest
from httpx import AsyncClient, ASGITransport
from demo_project.backend.main import app


@pytest.mark.anyio
async def test_create_appointment_correct_payload():
    """POST with the correct snake_case field names returns 200."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/appointments",
            json={"patient_id": 1, "doctor_id": 4},
        )
    assert response.status_code == 200
    data = response.json()
    assert data["patient_id"] == 1
    assert data["doctor_id"] == 4
    assert data["message"] == "Appointment created"


@pytest.mark.anyio
async def test_create_appointment_frontend_drift_bug():
    """POST with camelCase doctorId (frontend bug) returns 422 — doctor_id is required."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/appointments",
            json={"patient_id": 1, "doctorId": 4},  # <-- the frontend bug
        )
    assert response.status_code == 422
    errors = response.json()["detail"]
    field_errors = [e["loc"] for e in errors]
    # doctor_id must be flagged as missing
    assert any("doctor_id" in loc for loc in field_errors)


@pytest.mark.anyio
async def test_contract_doctor_id_field_name():
    """Regression: verify frontend sends 'doctor_id', not 'doctorId'."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/appointments",
            json={"patient_id": 99, "doctor_id": 1},
        )
    assert response.status_code == 200, (
        f"Contract regression: {response.status_code} — "
        f"ensure frontend sends 'doctor_id' not 'doctorId'"
    )
