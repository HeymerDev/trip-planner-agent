"""Lambda `trips`: CRUD de viajes y resumen de presupuesto (Tools create_trip / get_trips / update_trip)."""

import repo
from common import (
    ApiError,
    Fields,
    MAX_MONEY,
    check_date_range,
    check_id,
    make_handler,
    new_id,
    not_found,
    now_iso,
    parse_body,
    pk,
    response,
    table,
    v_date,
    v_enum,
    v_int,
    v_text,
)

TRIP_STATUSES = {"PLANEADO", "CONFIRMADO", "FINALIZADO", "CANCELADO"}


def _validate(data: dict, *, partial: bool, existing: dict | None = None) -> dict:
    """Valida el cuerpo de creacion (partial=False) o de actualizacion parcial (partial=True)."""
    f = Fields()
    required = not partial
    clean = {
        "name": v_text(f, data, "name", max_len=120, required=False),
        "origin": v_text(f, data, "origin", min_len=2, max_len=80, required=required),
        "destination": v_text(f, data, "destination", min_len=2, max_len=80, required=required),
        "startDate": v_date(f, data, "startDate", required=required),
        "endDate": v_date(f, data, "endDate", required=required),
        "travelers": v_int(f, data, "travelers", lo=1, hi=20, required=required),
        "budgetCOP": v_int(f, data, "budgetCOP", lo=0, hi=MAX_MONEY, required=required),
        "notes": v_text(f, data, "notes", min_len=0, max_len=1000, required=False),
        "status": v_enum(f, data, "status", TRIP_STATUSES, required=False),
    }
    start = clean["startDate"] or (existing or {}).get("startDate")
    end = clean["endDate"] or (existing or {}).get("endDate")
    check_date_range(f, start, end)
    f.raise_if_any()
    return {k: v for k, v in clean.items() if v is not None}


def _budget_summary(trip: dict, itinerary: dict | None, reservations: list[dict]) -> dict:
    active = [r for r in reservations if r.get("status") != "CANCELADA"]
    reserved = sum(int(r.get("priceCOP", 0)) for r in active)
    planned = 0
    if itinerary:
        for day in itinerary.get("days", []):
            planned += sum(int(item.get("costCOP", 0) or 0) for item in day.get("items", []))
    budget = int(trip["budgetCOP"])
    by_kind: dict[str, int] = {}
    for r in active:
        by_kind[r["kind"]] = by_kind.get(r["kind"], 0) + int(r.get("priceCOP", 0))
    return {
        "budgetCOP": budget,
        "reservedCOP": reserved,
        "plannedActivitiesCOP": planned,
        "remainingCOP": budget - reserved - planned,
        "reservedByKind": by_kind,
        "overBudget": reserved + planned > budget,
    }


def create_trip(event, sub):
    data = parse_body(event)
    clean = _validate(data, partial=False)
    trip_id = new_id()
    now = now_iso()
    item = {
        "PK": pk(sub),
        "SK": f"TRIP#{trip_id}",
        "name": clean.get("name") or f"Viaje a {clean['destination']}",
        "origin": clean["origin"],
        "destination": clean["destination"],
        "startDate": clean["startDate"],
        "endDate": clean["endDate"],
        "travelers": clean["travelers"],
        "budgetCOP": clean["budgetCOP"],
        "notes": clean.get("notes", ""),
        "status": clean.get("status", "PLANEADO"),
        "createdAt": now,
        "updatedAt": now,
    }
    table().put_item(Item=item, ConditionExpression="attribute_not_exists(PK)")
    return response(201, repo.trip_view(item))


def list_trips(event, sub):
    items = repo.query_prefix(sub, "TRIP#")
    trips = sorted((repo.trip_view(i) for i in items), key=lambda t: t["startDate"])
    return response(200, {"trips": trips})


def get_trip(event, sub):
    trip_id = check_id(event["pathParameters"].get("id"), "Viaje")
    item = repo.get_item(sub, f"TRIP#{trip_id}")
    if not item:
        raise not_found("Viaje")
    itinerary = repo.get_item(sub, f"ITIN#{trip_id}")
    reservations = [
        repo.reservation_view(i) for i in repo.query_prefix(sub, "RES#") if i.get("tripId") == trip_id
    ]
    trip = repo.trip_view(item)
    return response(
        200,
        {
            "trip": trip,
            "itinerary": repo.public(itinerary),
            "reservations": reservations,
            "budget": _budget_summary(trip, itinerary, reservations),
        },
    )


def update_trip(event, sub):
    trip_id = check_id(event["pathParameters"].get("id"), "Viaje")
    existing = repo.get_item(sub, f"TRIP#{trip_id}")
    if not existing:
        raise not_found("Viaje")
    clean = _validate(parse_body(event), partial=True, existing=existing)
    if not clean:
        raise ApiError(400, "VALIDATION_ERROR", "No hay campos para actualizar.")

    clean["updatedAt"] = now_iso()
    names = {f"#{k}": k for k in clean}
    values = {f":{k}": v for k, v in clean.items()}
    updated = table().update_item(
        Key={"PK": pk(sub), "SK": f"TRIP#{trip_id}"},
        UpdateExpression="SET " + ", ".join(f"#{k} = :{k}" for k in clean),
        ExpressionAttributeNames=names,
        ExpressionAttributeValues=values,
        ConditionExpression="attribute_exists(PK)",
        ReturnValues="ALL_NEW",
    )["Attributes"]
    return response(200, repo.trip_view(updated))


def delete_trip(event, sub):
    trip_id = check_id(event["pathParameters"].get("id"), "Viaje")
    if not repo.get_item(sub, f"TRIP#{trip_id}"):
        raise not_found("Viaje")
    # Las reservas del viaje no se borran (son registros de compra): quedan sin viaje asociado.
    for res in repo.query_prefix(sub, "RES#"):
        if res.get("tripId") == trip_id:
            table().update_item(
                Key={"PK": res["PK"], "SK": res["SK"]},
                UpdateExpression="REMOVE tripId SET updatedAt = :u",
                ExpressionAttributeValues={":u": now_iso()},
            )
    table().delete_item(Key={"PK": pk(sub), "SK": f"ITIN#{trip_id}"})
    table().delete_item(Key={"PK": pk(sub), "SK": f"TRIP#{trip_id}"})
    return response(200, {"deleted": True, "id": trip_id})


handler = make_handler(
    {
        "POST /trips": create_trip,
        "GET /trips": list_trips,
        "GET /trips/{id}": get_trip,
        "PATCH /trips/{id}": update_trip,
        "DELETE /trips/{id}": delete_trip,
    }
)
