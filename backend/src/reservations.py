"""Lambda `reservations`: reservas de vuelos, hoteles y actividades (Tools create/get/update_reservation)."""

from decimal import Decimal

from botocore.exceptions import ClientError

import repo
from common import (
    ApiError,
    Fields,
    MAX_MONEY,
    check_id,
    conflict,
    make_handler,
    new_id,
    not_found,
    now_iso,
    parse_body,
    pk,
    response,
    sanitize_json,
    table,
    transact,
    v_enum,
    v_int,
    v_text,
    v_url,
)

KINDS = {"FLIGHT", "HOTEL", "ACTIVITY"}
STATUSES = {"SIMULADA", "PENDIENTE", "CONFIRMADA", "CANCELADA"}
# Estados que el usuario o el agente pueden fijar. CONFIRMADA queda reservado a un proveedor real.
USER_SETTABLE = {"SIMULADA", "PENDIENTE", "CANCELADA"}
TRANSITIONS = {
    "SIMULADA": {"PENDIENTE", "CANCELADA"},
    "PENDIENTE": {"SIMULADA", "CANCELADA"},
    "CONFIRMADA": set(),
    "CANCELADA": set(),
}


def validate_reservation(data: dict, *, require_trip: bool = True) -> dict:
    """Valida el cuerpo de creacion de una reserva (usado tambien por /purchases)."""
    f = Fields()
    clean = {
        "tripId": v_text(f, data, "tripId", min_len=6, max_len=64, required=require_trip),
        "kind": v_enum(f, data, "kind", KINDS),
        "title": v_text(f, data, "title", max_len=160),
        "priceCOP": v_int(f, data, "priceCOP", lo=0, hi=MAX_MONEY),
        "link": v_url(f, data, "link"),
        "originalCurrency": v_text(f, data, "originalCurrency", min_len=3, max_len=3, required=False),
        "originalPrice": data.get("originalPrice"),
        "fxRate": data.get("fxRate"),
    }
    for name in ("originalPrice", "fxRate"):
        value = clean[name]
        if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0):
            f.add(name, "Debe ser un numero positivo.")
        else:
            clean[name] = Decimal(str(value)) if value is not None else None
    details = data.get("details", {})
    if not isinstance(details, dict):
        f.add("details", "Debe ser un objeto.")
        details = {}
    clean["details"] = sanitize_json(details)
    f.raise_if_any()
    return clean


def build_reservation_item(sub: str, res_id: str, clean: dict, *, status: str, paid: bool) -> dict:
    now = now_iso()
    item = {
        "PK": pk(sub),
        "SK": f"RES#{res_id}",
        "tripId": clean["tripId"],
        "kind": clean["kind"],
        "title": clean["title"],
        "priceCOP": clean["priceCOP"],
        "details": clean["details"],
        "status": status,
        "paid": paid,
        "createdAt": now,
        "updatedAt": now,
    }
    for optional in ("link", "originalCurrency", "originalPrice", "fxRate"):
        if clean.get(optional) is not None:
            item[optional] = clean[optional]
    return item


def require_trip(sub: str, trip_id: str) -> dict:
    trip = repo.get_item(sub, f"TRIP#{trip_id}")
    if not trip:
        raise ApiError(404, "TRIP_NOT_FOUND", "El viaje indicado no existe.")
    return trip


def create_reservation(event, sub):
    data = parse_body(event)
    clean = validate_reservation(data)
    f = Fields()
    status = v_enum(f, data, "status", {"SIMULADA", "PENDIENTE"}, required=False, default="SIMULADA")
    f.raise_if_any()
    require_trip(sub, clean["tripId"])

    item = build_reservation_item(sub, new_id(), clean, status=status, paid=False)
    table().put_item(Item=item, ConditionExpression="attribute_not_exists(PK)")
    return response(201, repo.reservation_view(item))


def list_reservations(event, sub):
    params = event.get("queryStringParameters") or {}
    trip_id, status = params.get("tripId"), params.get("status")
    if status and status not in STATUSES:
        raise ApiError(400, "VALIDATION_ERROR", "Estado invalido.", {"status": "Valor no permitido."})
    items = [repo.reservation_view(i) for i in repo.query_prefix(sub, "RES#")]
    if trip_id:
        items = [i for i in items if i.get("tripId") == trip_id]
    if status:
        items = [i for i in items if i["status"] == status]
    items.sort(key=lambda r: r["createdAt"], reverse=True)
    return response(200, {"reservations": items})


def _load(event, sub) -> tuple[str, dict]:
    res_id = check_id(event["pathParameters"].get("id"), "Reserva")
    item = repo.get_item(sub, f"RES#{res_id}")
    if not item:
        raise not_found("Reserva")
    return res_id, item


def get_reservation(event, sub):
    _, item = _load(event, sub)
    return response(200, repo.reservation_view(item))


def _cancel_with_refund(sub: str, res_id: str, item: dict) -> None:
    """Cancela una reserva pagada y devuelve el dinero en UNA transaccion (sin doble reembolso)."""
    now = now_iso()
    amount = int(item["priceCOP"])
    transact(
        [
            {
                "Update": {
                    "Key": {"PK": pk(sub), "SK": f"RES#{res_id}"},
                    "UpdateExpression": "SET #s = :c, updatedAt = :u, refunded = :t",
                    "ConditionExpression": "#s <> :c AND paid = :t AND attribute_not_exists(refunded)",
                    "ExpressionAttributeNames": {"#s": "status"},
                    "ExpressionAttributeValues": {":c": "CANCELADA", ":u": now, ":t": True},
                }
            },
            {
                "Update": {
                    "Key": {"PK": pk(sub), "SK": "WALLET"},
                    "UpdateExpression": "ADD balanceCOP :a SET updatedAt = :u",
                    "ExpressionAttributeValues": {":a": amount, ":u": now},
                }
            },
            {
                "Put": {
                    "Item": {
                        "PK": pk(sub),
                        "SK": f"TXN#{now}#{new_id()}",
                        "type": "REFUND",
                        "amountCOP": amount,
                        "reservationId": res_id,
                        "title": item["title"],
                        "createdAt": now,
                    },
                    "ConditionExpression": "attribute_not_exists(PK)",
                }
            },
        ]
    )


def update_reservation(event, sub):
    res_id, item = _load(event, sub)
    data = parse_body(event)
    f = Fields()
    changes: dict = {}

    if "title" in data:
        changes["title"] = v_text(f, data, "title", max_len=160)
    if "link" in data:
        changes["link"] = v_url(f, data, "link")
    if "details" in data:
        if isinstance(data["details"], dict):
            changes["details"] = sanitize_json(data["details"])
        else:
            f.add("details", "Debe ser un objeto.")
    if "priceCOP" in data:
        price = v_int(f, data, "priceCOP", lo=0, hi=MAX_MONEY)
        if item.get("paid") and price is not None and price != int(item["priceCOP"]):
            raise conflict("PAID_RESERVATION", "No se puede cambiar el precio de una reserva ya pagada.")
        changes["priceCOP"] = price
    new_status = v_enum(f, data, "status", STATUSES, required=False)
    new_trip = data.get("tripId", "__keep__")
    if new_trip not in ("__keep__", None):
        new_trip = v_text(f, data, "tripId", min_len=6, max_len=64)
    f.raise_if_any()

    if new_trip != "__keep__":
        if new_trip is not None:
            require_trip(sub, new_trip)
        changes["tripId"] = new_trip

    if new_status and new_status != item["status"]:
        if new_status == "CONFIRMADA":
            raise conflict("PROVIDER_ONLY", "Solo un proveedor real puede confirmar una reserva.")
        if new_status not in TRANSITIONS[item["status"]]:
            raise conflict("INVALID_TRANSITION", f"No se puede pasar de {item['status']} a {new_status}.")
        if new_status == "CANCELADA" and item.get("paid"):
            # Aplica antes los demas cambios y luego reembolsa de forma atomica.
            _apply_changes(sub, res_id, changes)
            try:
                _cancel_with_refund(sub, res_id, item)
            except ClientError as error:
                if error.response["Error"]["Code"] == "TransactionCanceledException":
                    raise conflict("ALREADY_REFUNDED", "La reserva ya fue cancelada y reembolsada.")
                raise
            return response(200, repo.reservation_view(repo.get_item(sub, f"RES#{res_id}")))
        changes["status"] = new_status

    if not changes:
        if new_status and new_status == item["status"]:
            return response(200, repo.reservation_view(item))  # idempotente: ya esta en ese estado
        raise ApiError(400, "VALIDATION_ERROR", "No hay cambios para aplicar.")
    updated = _apply_changes(sub, res_id, changes)
    return response(200, repo.reservation_view(updated))


def _apply_changes(sub: str, res_id: str, changes: dict) -> dict:
    sets = {k: v for k, v in changes.items() if v is not None}
    removes = [k for k, v in changes.items() if v is None]
    sets["updatedAt"] = now_iso()
    expression = "SET " + ", ".join(f"#{k} = :{k}" for k in sets)
    if removes:
        expression += " REMOVE " + ", ".join(f"#{k}" for k in removes)
    names = {f"#{k}": k for k in [*sets, *removes]}
    return table().update_item(
        Key={"PK": pk(sub), "SK": f"RES#{res_id}"},
        UpdateExpression=expression,
        ExpressionAttributeNames=names,
        ExpressionAttributeValues={f":{k}": v for k, v in sets.items()},
        ConditionExpression="attribute_exists(PK)",
        ReturnValues="ALL_NEW",
    )["Attributes"]


handler = make_handler(
    {
        "POST /reservations": create_reservation,
        "GET /reservations": list_reservations,
        "GET /reservations/{id}": get_reservation,
        "PATCH /reservations/{id}": update_reservation,
    }
)
