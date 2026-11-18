"""Acceso a la tabla unica: consultas por prefijo de SK y lecturas tipadas por usuario."""

from boto3.dynamodb.conditions import Key

from common import pk, strip_keys, table


def query_prefix(sub: str, prefix: str, *, newest_first: bool = False, limit: int | None = None) -> list[dict]:
    """Todos los items del usuario cuya SK empieza por `prefix` (maneja paginacion)."""
    items: list[dict] = []
    kwargs = {
        "KeyConditionExpression": Key("PK").eq(pk(sub)) & Key("SK").begins_with(prefix),
        "ScanIndexForward": not newest_first,
    }
    if limit:
        kwargs["Limit"] = limit
    while True:
        result = table().query(**kwargs)
        items.extend(result.get("Items", []))
        if limit and len(items) >= limit:
            return items[:limit]
        last = result.get("LastEvaluatedKey")
        if not last:
            return items
        kwargs["ExclusiveStartKey"] = last


def get_item(sub: str, sk: str) -> dict | None:
    return table().get_item(Key={"PK": pk(sub), "SK": sk}).get("Item")


def public(item: dict | None) -> dict | None:
    return strip_keys(item)


def trip_view(item: dict) -> dict:
    """Viaje listo para el cliente (id legible, sin claves internas)."""
    view = strip_keys(item)
    view["id"] = item["SK"].split("#", 1)[1]
    return view


def reservation_view(item: dict) -> dict:
    view = strip_keys(item)
    view["id"] = item["SK"].split("#", 1)[1]
    return view


def wallet_balance(sub: str) -> int:
    item = get_item(sub, "WALLET")
    return int(item["balanceCOP"]) if item else 0
