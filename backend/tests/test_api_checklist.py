from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_checklist_endpoint_happy_path():
    resp = client.post(
        "/api/checklist",
        json={
            "ownership": "rent",
            "has_pets": True,
            "mobility_needs": False,
            "construction_type": "wood_siding_or_shake_roof",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["defensible_space"]) > 0
    assert len(body["go_bag"]) > 0
    assert len(body["evacuation_route"]) > 0
    assert any("renter" in item["reasons"] for item in body["defensible_space"])
    assert any("pet_owner" in item["reasons"] for item in body["go_bag"])
    assert "does not reflect any specific active fire" in body["note"]


def test_checklist_endpoint_defaults_construction_type():
    resp = client.post(
        "/api/checklist",
        json={"ownership": "own", "has_pets": False, "mobility_needs": False},
    )
    assert resp.status_code == 200


def test_checklist_endpoint_rejects_invalid_ownership():
    resp = client.post(
        "/api/checklist",
        json={"ownership": "lease-to-own", "has_pets": False, "mobility_needs": False},
    )
    assert resp.status_code == 422
