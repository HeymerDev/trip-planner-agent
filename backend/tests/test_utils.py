"""Pruebas de divisas y comparador bus/avion (sin red: se simulan las APIs externas)."""

import pytest

import utils
from conftest import call

FX_PAYLOAD = {"result": "success", "time_last_update_utc": "Mon, 16 Nov 2026 00:00:01 +0000", "rates": {"COP": 4000.0, "USD": 1.0}}

CITIES = {
    "Bogota": {"results": [{"name": "Bogota", "country": "Colombia", "latitude": 4.6097, "longitude": -74.0817}]},
    "Cartagena": {"results": [{"name": "Cartagena", "country": "Colombia", "latitude": 10.3910, "longitude": -75.4794}]},
    "Manizales": {"results": [{"name": "Manizales", "country": "Colombia", "latitude": 5.0703, "longitude": -75.5138}]},
    "Pereira": {"results": [{"name": "Pereira", "country": "Colombia", "latitude": 4.8133, "longitude": -75.6961}]},
}


@pytest.fixture(autouse=True)
def fake_http(monkeypatch):
    def fake(url):
        if "open.er-api.com" in url:
            return FX_PAYLOAD
        for name, payload in CITIES.items():
            if f"name={name}" in url:
                return payload
        return {}

    monkeypatch.setattr(utils, "_get_json", fake)


def test_fx_convierte_y_valida():
    status, data = call("utils", "GET /fx", query={"from": "usd", "to": "cop", "amount": "100"})
    assert status == 200 and data["result"] == 400000.0 and data["rate"] == 4000.0 and data["source"]
    assert call("utils", "GET /fx", query={"from": "US", "to": "COP"})[0] == 400
    assert call("utils", "GET /fx", query={"from": "USD", "to": "COP", "amount": "-5"})[0] == 400
    assert call("utils", "GET /fx", query={"from": "USD", "to": "XXX"})[0] == 400  # sin tasa
    assert call("utils", "GET /fx", query={"from": "USD", "to": "COP"}, sub=None)[0] == 401


def test_bogota_cartagena_recomienda_avion():
    status, data = call("utils", "GET /transport", query={"origin": "Bogota", "destination": "Cartagena"})
    assert status == 200 and data["recommendation"] == "AVION"
    assert data["bus"]["isEstimate"] is True and data["bus"]["hours"] > data["flight"]["hours"]


def test_ciudades_cercanas_recomienda_bus():
    status, data = call("utils", "GET /transport", query={"origin": "Manizales", "destination": "Pereira"})
    assert status == 200 and data["recommendation"] == "BUS"
    assert data["distanceKm"] < 100


def test_ciudad_inexistente_y_parametros_invalidos():
    assert call("utils", "GET /transport", query={"origin": "Atlantis", "destination": "Bogota"})[0] == 404
    assert call("utils", "GET /transport", query={"origin": "B"})[0] == 400


def test_haversine():
    assert 600 < utils.haversine_km(4.6097, -74.0817, 10.3910, -75.4794) < 700
