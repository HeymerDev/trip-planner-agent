"""Pruebas de reglas de negocio, validacion, aislamiento por usuario y atomicidad (T-17, T-73)."""

from conftest import USER_A, USER_B, call, make_trip, top_up


def flight_body(trip_id, price=400_000, **extra):
    return {
        "tripId": trip_id,
        "kind": "FLIGHT",
        "title": "BOG-CTG LATAM",
        "priceCOP": price,
        "details": {"airline": "LATAM", "departure": "2026-12-10T07:40"},
        "link": "https://www.google.com/travel/flights?x=1",
        **extra,
    }


# ------------------------------------------------------------------------------ seguridad


def test_sin_token_devuelve_401():
    status, data = call("trips", "GET /trips", sub=None)
    assert status == 401
    assert data["error"]["code"] == "UNAUTHORIZED"


def test_ruta_desconocida_404():
    status, _ = call("trips", "GET /otra")
    assert status == 404


def test_usuario_no_ve_ni_modifica_viajes_ajenos():
    trip = make_trip(sub=USER_A)
    assert call("trips", "GET /trips/{id}", sub=USER_B, path={"id": trip["id"]})[0] == 404
    assert call("trips", "PATCH /trips/{id}", sub=USER_B, path={"id": trip["id"]}, body={"name": "x"})[0] == 404
    assert call("trips", "DELETE /trips/{id}", sub=USER_B, path={"id": trip["id"]})[0] == 404
    assert call("trips", "GET /trips", sub=USER_B)[1]["trips"] == []
    # El dueno sigue viendolo intacto
    assert call("trips", "GET /trips/{id}", sub=USER_A, path={"id": trip["id"]})[0] == 200


def test_el_cuerpo_no_puede_cambiar_el_dueno():
    """Un `PK`/`userId` en el cuerpo se ignora: el usuario sale siempre del token."""
    status, trip = call(
        "trips",
        "POST /trips",
        sub=USER_A,
        body={
            "origin": "Bogota", "destination": "Cali", "startDate": "2026-12-10", "endDate": "2026-12-12",
            "travelers": 1, "budgetCOP": 1, "PK": "USER#otro", "userId": USER_B,
        },
    )
    assert status == 201
    assert call("trips", "GET /trips", sub=USER_B)[1]["trips"] == []
    assert len(call("trips", "GET /trips", sub=USER_A)[1]["trips"]) == 1
    assert "PK" not in trip and "SK" not in trip


def test_reserva_ajena_404_y_no_se_asocia_a_viaje_ajeno():
    trip_a = make_trip(sub=USER_A)
    top_up(1_000_000, sub=USER_A)
    _, bought = call("wallet", "POST /purchases", sub=USER_A, body=flight_body(trip_a["id"]))
    res_id = bought["reservation"]["id"]
    assert call("reservations", "GET /reservations/{id}", sub=USER_B, path={"id": res_id})[0] == 404
    assert call("reservations", "PATCH /reservations/{id}", sub=USER_B, path={"id": res_id}, body={"title": "x"})[0] == 404
    # B no puede crear una reserva sobre el viaje de A
    status, data = call("reservations", "POST /reservations", sub=USER_B, body=flight_body(trip_a["id"]))
    assert status == 404 and data["error"]["code"] == "TRIP_NOT_FOUND"


# ----------------------------------------------------------------------------- validacion


def test_viaje_invalido_lista_todos_los_campos():
    status, data = call(
        "trips", "POST /trips",
        body={"origin": "B", "destination": "", "startDate": "2026-13-40", "endDate": "x", "travelers": 0, "budgetCOP": -5},
    )
    assert status == 400
    assert data["error"]["code"] == "VALIDATION_ERROR"
    assert {"origin", "destination", "startDate", "endDate", "travelers", "budgetCOP"} <= set(data["error"]["fields"])


def test_fechas_invertidas_y_viaje_demasiado_largo():
    bad = {"origin": "Bogota", "destination": "Cali", "travelers": 1, "budgetCOP": 10}
    s1, d1 = call("trips", "POST /trips", body={**bad, "startDate": "2026-12-10", "endDate": "2026-12-01"})
    s2, d2 = call("trips", "POST /trips", body={**bad, "startDate": "2026-01-01", "endDate": "2026-06-01"})
    assert s1 == 400 and "endDate" in d1["error"]["fields"]
    assert s2 == 400 and "endDate" in d2["error"]["fields"]


def test_json_invalido_y_cuerpo_no_objeto():
    assert call("trips", "POST /trips", raw_body="{no json")[0] == 400
    assert call("trips", "POST /trips", raw_body="[1,2]")[0] == 400


def test_travelers_booleano_o_decimal_se_rechaza():
    base = {"origin": "Bogota", "destination": "Cali", "startDate": "2026-12-10", "endDate": "2026-12-12", "budgetCOP": 1}
    assert call("trips", "POST /trips", body={**base, "travelers": True})[0] == 400
    assert call("trips", "POST /trips", body={**base, "travelers": 2.5})[0] == 400


def test_id_con_formato_invalido_404():
    assert call("trips", "GET /trips/{id}", path={"id": "../../x"})[0] == 404


def test_reserva_valida_tipo_y_url():
    trip = make_trip()
    status, data = call(
        "reservations", "POST /reservations",
        body={"tripId": trip["id"], "kind": "TAXI", "title": "x", "priceCOP": 10, "link": "javascript:alert(1)"},
    )
    assert status == 400
    assert {"kind", "link"} <= set(data["error"]["fields"])


# ---------------------------------------------------------------------------------- viajes


def test_crud_de_viaje_y_nombre_por_defecto():
    trip = make_trip()
    assert trip["name"] == "Viaje a Cartagena"
    assert trip["status"] == "PLANEADO"
    status, updated = call("trips", "PATCH /trips/{id}", path={"id": trip["id"]}, body={"budgetCOP": 6_000_000, "status": "CONFIRMADO"})
    assert status == 200 and updated["budgetCOP"] == 6_000_000 and updated["status"] == "CONFIRMADO"
    # El PATCH valida contra las fechas existentes
    status, data = call("trips", "PATCH /trips/{id}", path={"id": trip["id"]}, body={"endDate": "2026-12-01"})
    assert status == 400 and "endDate" in data["error"]["fields"]
    assert call("trips", "PATCH /trips/{id}", path={"id": trip["id"]}, body={})[0] == 400
    assert call("trips", "DELETE /trips/{id}", path={"id": trip["id"]})[0] == 200
    assert call("trips", "GET /trips/{id}", path={"id": trip["id"]})[0] == 404


# ------------------------------------------------------------------------------ itinerario


def days(*dates):
    return [{"date": d, "items": [{"time": "15:00", "title": "Tarde", "costCOP": 50_000}, {"time": "09:00", "title": "Manana"}]} for d in dates]


def test_itinerario_crear_ordenar_y_conflicto():
    trip = make_trip()
    path = {"id": trip["id"]}
    status, data = call("itineraries", "POST /trips/{id}/itinerary", path=path, body={"days": days("2026-12-11", "2026-12-10")})
    assert status == 201
    assert [d["date"] for d in data["days"]] == ["2026-12-10", "2026-12-11"]
    assert [i["time"] for i in data["days"][0]["items"]] == ["09:00", "15:00"]
    assert call("itineraries", "POST /trips/{id}/itinerary", path=path, body={"days": days("2026-12-10")})[0] == 409
    status, data = call("itineraries", "PUT /trips/{id}/itinerary", path=path, body={"days": days("2026-12-12")})
    assert status == 200 and len(data["days"]) == 1
    assert call("itineraries", "GET /trips/{id}/itinerary", path=path)[1]["days"][0]["date"] == "2026-12-12"


def test_itinerario_fuera_de_fechas_o_invalido():
    trip = make_trip()
    path = {"id": trip["id"]}
    assert call("itineraries", "PUT /trips/{id}/itinerary", path=path, body={"days": days("2027-01-01")})[0] == 400
    assert call("itineraries", "PUT /trips/{id}/itinerary", path=path, body={"days": days("2026-12-10", "2026-12-10")})[0] == 400
    assert call("itineraries", "PUT /trips/{id}/itinerary", path=path, body={"days": []})[0] == 400
    bad_time = [{"date": "2026-12-10", "items": [{"time": "25:99", "title": "x"}]}]
    assert call("itineraries", "PUT /trips/{id}/itinerary", path=path, body={"days": bad_time})[0] == 400


def test_itinerario_de_viaje_ajeno_404():
    trip = make_trip(sub=USER_A)
    status, _ = call("itineraries", "PUT /trips/{id}/itinerary", sub=USER_B, path={"id": trip["id"]}, body={"days": days("2026-12-10")})
    assert status == 404


# -------------------------------------------------------------------------------- reservas


def test_reserva_simulada_estados_y_reasociacion():
    trip, other = make_trip(), make_trip(destination="Medellin")
    status, res = call("reservations", "POST /reservations", body=flight_body(trip["id"]))
    assert status == 201 and res["status"] == "SIMULADA" and res["paid"] is False
    path = {"id": res["id"]}

    assert call("reservations", "PATCH /reservations/{id}", path=path, body={"status": "PENDIENTE"})[1]["status"] == "PENDIENTE"
    status, data = call("reservations", "PATCH /reservations/{id}", path=path, body={"status": "CONFIRMADA"})
    assert status == 409 and data["error"]["code"] == "PROVIDER_ONLY"
    moved = call("reservations", "PATCH /reservations/{id}", path=path, body={"tripId": other["id"]})[1]
    assert moved["tripId"] == other["id"]
    assert call("reservations", "PATCH /reservations/{id}", path=path, body={"tripId": "no-existe-123"})[0] == 404

    assert call("reservations", "GET /reservations", query={"tripId": other["id"]})[1]["reservations"][0]["id"] == res["id"]
    assert call("reservations", "GET /reservations", query={"tripId": trip["id"]})[1]["reservations"] == []
    assert call("reservations", "GET /reservations", query={"status": "NOPE"})[0] == 400

    assert call("reservations", "PATCH /reservations/{id}", path=path, body={"status": "CANCELADA"})[1]["status"] == "CANCELADA"
    status, data = call("reservations", "PATCH /reservations/{id}", path=path, body={"status": "SIMULADA"})
    assert status == 409 and data["error"]["code"] == "INVALID_TRANSITION"


def test_crear_reserva_no_permite_estado_confirmada():
    trip = make_trip()
    assert call("reservations", "POST /reservations", body=flight_body(trip["id"], status="CONFIRMADA"))[0] == 400


# ------------------------------------------------------------------------------- monedero


def test_recarga_valida_rango_y_tope():
    assert call("wallet", "POST /wallet/topup", body={"amountCOP": 10})[0] == 400
    assert call("wallet", "POST /wallet/topup", body={"amountCOP": 99_000_000})[0] == 400
    top_up(10_000_000)
    wallet = call("wallet", "GET /wallet")[1]
    assert wallet["balanceCOP"] == 10_000_000
    assert wallet["transactions"][0]["type"] == "TOPUP"
    for _ in range(9):
        top_up(10_000_000)
    status, data = call("wallet", "POST /wallet/topup", body={"amountCOP": 1_000})
    assert status == 409 and data["error"]["code"] == "BALANCE_LIMIT"


def test_compra_descuenta_crea_reserva_y_movimiento():
    trip = make_trip()
    top_up(1_000_000)
    status, data = call("wallet", "POST /purchases", body=flight_body(trip["id"], 400_000))
    assert status == 201
    assert data["balanceCOP"] == 600_000
    res = data["reservation"]
    assert res["status"] == "SIMULADA" and res["paid"] is True
    wallet = call("wallet", "GET /wallet")[1]
    assert [t["type"] for t in wallet["transactions"]][:2] == ["PURCHASE", "TOPUP"]
    assert wallet["transactions"][0]["amountCOP"] == -400_000
    # y el viaje refleja el gasto en su presupuesto
    summary = call("trips", "GET /trips/{id}", path={"id": trip["id"]})[1]["budget"]
    assert summary["reservedCOP"] == 400_000 and summary["remainingCOP"] == 4_600_000


def test_saldo_insuficiente_no_cambia_nada():
    trip = make_trip()
    top_up(100_000)
    status, data = call("wallet", "POST /purchases", body=flight_body(trip["id"], 400_000))
    assert status == 409 and data["error"]["code"] == "INSUFFICIENT_FUNDS"
    assert call("wallet", "GET /wallet")[1]["balanceCOP"] == 100_000
    assert call("reservations", "GET /reservations")[1]["reservations"] == []


def test_compra_sin_monedero_creado_es_saldo_insuficiente():
    trip = make_trip()
    status, data = call("wallet", "POST /purchases", body=flight_body(trip["id"], 1_000))
    assert status == 409 and data["error"]["code"] == "INSUFFICIENT_FUNDS"


def test_idempotencia_no_cobra_dos_veces():
    trip = make_trip()
    top_up(1_000_000)
    body = flight_body(trip["id"], 300_000, idempotencyKey="compra-vuelo-0001")
    assert call("wallet", "POST /purchases", body=body)[0] == 201
    status, data = call("wallet", "POST /purchases", body=body)
    assert status == 409 and data["error"]["code"] == "DUPLICATE"
    assert call("wallet", "GET /wallet")[1]["balanceCOP"] == 700_000
    assert len(call("reservations", "GET /reservations")[1]["reservations"]) == 1


def test_misma_clave_de_idempotencia_en_otro_usuario_no_colisiona():
    for sub in (USER_A, USER_B):
        trip = make_trip(sub=sub)
        top_up(500_000, sub=sub)
        body = flight_body(trip["id"], 100_000, idempotencyKey="clave-compartida-1")
        assert call("wallet", "POST /purchases", sub=sub, body=body)[0] == 201


def test_cancelar_reserva_pagada_reembolsa_una_sola_vez():
    trip = make_trip()
    top_up(1_000_000)
    res = call("wallet", "POST /purchases", body=flight_body(trip["id"], 400_000))[1]["reservation"]
    path = {"id": res["id"]}
    status, data = call("reservations", "PATCH /reservations/{id}", path=path, body={"status": "CANCELADA"})
    assert status == 200 and data["status"] == "CANCELADA"
    assert call("wallet", "GET /wallet")[1]["balanceCOP"] == 1_000_000
    # segundo intento: no hay doble reembolso
    status, _ = call("reservations", "PATCH /reservations/{id}", path=path, body={"status": "CANCELADA"})
    assert status == 200
    assert call("wallet", "GET /wallet")[1]["balanceCOP"] == 1_000_000
    types = [t["type"] for t in call("wallet", "GET /wallet")[1]["transactions"]]
    assert types.count("REFUND") == 1


def test_no_se_puede_cambiar_el_precio_de_una_reserva_pagada():
    trip = make_trip()
    top_up(1_000_000)
    res = call("wallet", "POST /purchases", body=flight_body(trip["id"], 400_000))[1]["reservation"]
    status, data = call("reservations", "PATCH /reservations/{id}", path={"id": res["id"]}, body={"priceCOP": 1})
    assert status == 409 and data["error"]["code"] == "PAID_RESERVATION"


def test_compra_con_precio_cero_o_viaje_inexistente():
    trip = make_trip()
    top_up(100_000)
    assert call("wallet", "POST /purchases", body=flight_body(trip["id"], 0))[0] == 400
    assert call("wallet", "POST /purchases", body=flight_body("no-existe-1234", 10))[0] == 404


# ---------------------------------------------------------------------------- perfil y panel


def test_perfil_preferencias_y_dashboard():
    status, me = call("me", "GET /me")
    assert status == 200 and me["id"] == USER_A
    assert call("me", "PUT /me", body={"name": "Ana", "email": "ana@example.com"})[1]["name"] == "Ana"
    assert call("me", "PUT /me", body={"email": "sin-arroba"})[0] == 400

    prefs = {"defaultBudgetCOP": 3_000_000, "activities": ["playa", "cultura"], "airlines": ["LATAM"], "restrictions": "sin escalas"}
    assert call("me", "PUT /me/preferences", body=prefs)[1]["activities"] == ["playa", "cultura"]
    assert call("me", "GET /me/preferences")[1]["airlines"] == ["LATAM"]
    assert call("me", "PUT /me/preferences", body={"activities": ["bungee"]})[0] == 400

    trip = make_trip(startDate="2099-01-10", endDate="2099-01-12")
    top_up(500_000)
    call("wallet", "POST /purchases", body=flight_body(trip["id"], 100_000))
    dash = call("me", "GET /dashboard")[1]
    assert dash["counts"] == {"trips": 1, "reservations": 1}
    assert dash["walletBalanceCOP"] == 400_000
    assert dash["upcomingTrips"][0]["id"] == trip["id"]
    # Otro usuario ve su propio panel vacio
    assert call("me", "GET /dashboard", sub=USER_B)[1]["counts"] == {"trips": 0, "reservations": 0}


def test_eliminar_viaje_conserva_reservas_sin_viaje():
    trip = make_trip()
    top_up(500_000)
    res = call("wallet", "POST /purchases", body=flight_body(trip["id"], 100_000))[1]["reservation"]
    call("trips", "DELETE /trips/{id}", path={"id": trip["id"]})
    kept = call("reservations", "GET /reservations/{id}", path={"id": res["id"]})[1]
    assert "tripId" not in kept
