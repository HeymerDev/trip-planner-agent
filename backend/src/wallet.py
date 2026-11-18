"""
Lambda `wallet`: monedero simulado (saldo, recarga, historial) y compra atomica de reservas.

No existe ningun dato de tarjeta ni de pago: la recarga solo recibe un monto en COP.
"""

from botocore.exceptions import ClientError

import repo
from common import (
    ApiError,
    Fields,
    cancellation_codes,
    conflict,
    derive_id,
    make_handler,
    new_id,
    now_iso,
    parse_body,
    pk,
    response,
    strip_keys,
    transact,
    v_int,
    v_text,
)
from reservations import build_reservation_item, require_trip, validate_reservation

MIN_TOPUP = 1_000
MAX_TOPUP = 10_000_000
MAX_BALANCE = 100_000_000


def cop(value: int) -> str:
    """1234567 -> '1.234.567 COP' (separador de miles colombiano)."""
    return f"{value:,}".replace(",", ".") + " COP"


def _txn_view(item: dict) -> dict:
    view = strip_keys(item)
    view["id"] = item["SK"].split("#", 2)[2]
    return view


def get_wallet(event, sub):
    txns = repo.query_prefix(sub, "TXN#", newest_first=True, limit=30)
    return response(200, {"balanceCOP": repo.wallet_balance(sub), "transactions": [_txn_view(t) for t in txns]})


def topup(event, sub):
    data = parse_body(event)
    f = Fields()
    amount = v_int(f, data, "amountCOP", lo=MIN_TOPUP, hi=MAX_TOPUP)
    f.raise_if_any()
    now = now_iso()
    try:
        transact(
            [
                {
                    "Update": {
                        "Key": {"PK": pk(sub), "SK": "WALLET"},
                        "UpdateExpression": "ADD balanceCOP :a SET updatedAt = :u",
                        # Tope de saldo para que la simulacion no acumule cifras absurdas.
                        "ConditionExpression": "attribute_not_exists(balanceCOP) OR balanceCOP <= :lim",
                        "ExpressionAttributeValues": {":a": amount, ":u": now, ":lim": MAX_BALANCE - amount},
                    }
                },
                {
                    "Put": {
                        "Item": {
                            "PK": pk(sub),
                            "SK": f"TXN#{now}#{new_id()}",
                            "type": "TOPUP",
                            "amountCOP": amount,
                            "title": "Recarga simulada",
                            "createdAt": now,
                        },
                        "ConditionExpression": "attribute_not_exists(PK)",
                    }
                },
            ]
        )
    except ClientError as error:
        if error.response["Error"]["Code"] == "TransactionCanceledException":
            raise conflict("BALANCE_LIMIT", f"El saldo no puede superar {cop(MAX_BALANCE)}.")
        raise
    return get_wallet(event, sub) | {"statusCode": 201}


def purchase(event, sub):
    """Compra simulada: descuenta saldo + crea la reserva + registra el movimiento, todo o nada."""
    data = parse_body(event)
    clean = validate_reservation(data)
    f = Fields()
    key = v_text(f, data, "idempotencyKey", min_len=8, max_len=100, required=False)
    f.raise_if_any()
    require_trip(sub, clean["tripId"])

    price = int(clean["priceCOP"])
    if price <= 0:
        raise ApiError(400, "VALIDATION_ERROR", "El precio debe ser mayor que cero.", {"priceCOP": "Debe ser > 0."})
    res_id = derive_id(sub, key) if key else new_id()
    item = build_reservation_item(sub, res_id, clean, status="SIMULADA", paid=True)
    now = item["createdAt"]

    try:
        transact(
            [
                {
                    "Update": {
                        "Key": {"PK": pk(sub), "SK": "WALLET"},
                        "UpdateExpression": "SET balanceCOP = balanceCOP - :p, updatedAt = :u",
                        "ConditionExpression": "attribute_exists(balanceCOP) AND balanceCOP >= :p",
                        "ExpressionAttributeValues": {":p": price, ":u": now},
                    }
                },
                {"Put": {"Item": item, "ConditionExpression": "attribute_not_exists(PK)"}},
                {
                    "Put": {
                        "Item": {
                            "PK": pk(sub),
                            "SK": f"TXN#{now}#{new_id()}",
                            "type": "PURCHASE",
                            "amountCOP": -price,
                            "reservationId": res_id,
                            "title": clean["title"],
                            "createdAt": now,
                        },
                        "ConditionExpression": "attribute_not_exists(PK)",
                    }
                },
            ]
        )
    except ClientError as error:
        if error.response["Error"]["Code"] != "TransactionCanceledException":
            raise
        codes = cancellation_codes(error)
        if len(codes) > 1 and codes[1] == "ConditionalCheckFailed":
            raise conflict("DUPLICATE", "Esta compra ya fue registrada; no se cobro de nuevo.")
        if codes and codes[0] == "ConditionalCheckFailed":
            raise conflict(
                "INSUFFICIENT_FUNDS",
                f"Saldo insuficiente: la compra cuesta {cop(price)} y tu saldo es {cop(repo.wallet_balance(sub))}. "
                "Recarga el monedero e intenta de nuevo.",
            )
        raise
    return response(201, {"reservation": repo.reservation_view(item), "balanceCOP": repo.wallet_balance(sub)})


handler = make_handler(
    {
        "GET /wallet": get_wallet,
        "POST /wallet/topup": topup,
        "POST /purchases": purchase,
    }
)
