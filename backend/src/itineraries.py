"""Lambda `itineraries`: itinerario por dias de un viaje (Tools create_itinerary / update_itinerary)."""

from botocore.exceptions import ClientError

import repo
from common import (
    Fields,
    MAX_MONEY,
    TIME_RE,
    check_id,
    conflict,
    make_handler,
    not_found,
    now_iso,
    parse_body,
    pk,
    response,
    table,
    v_date,
    v_int,
    v_text,
)

MAX_DAYS = 31
MAX_ITEMS_PER_DAY = 20


def _validate_days(data: dict, trip: dict) -> list[dict]:
    f = Fields()
    days = data.get("days")
    if not isinstance(days, list) or not days:
        f.add("days", "Debe ser una lista con al menos un dia.")
        f.raise_if_any()
    if len(days) > MAX_DAYS:
        f.add("days", f"Maximo {MAX_DAYS} dias.")
        f.raise_if_any()

    clean_days, seen = [], set()
    for d_index, day in enumerate(days):
        prefix = f"days[{d_index}]"
        if not isinstance(day, dict):
            f.add(prefix, "Cada dia debe ser un objeto.")
            continue
        date_value = v_date(f, day, "date")
        if date_value:
            if date_value in seen:
                f.add(f"{prefix}.date", "Fecha repetida.")
            seen.add(date_value)
            if not trip["startDate"] <= date_value <= trip["endDate"]:
                f.add(f"{prefix}.date", "Debe estar dentro de las fechas del viaje.")
        items = day.get("items", [])
        if not isinstance(items, list) or len(items) > MAX_ITEMS_PER_DAY:
            f.add(f"{prefix}.items", f"Lista de hasta {MAX_ITEMS_PER_DAY} actividades.")
            continue
        clean_items = []
        for i_index, item in enumerate(items):
            ip = f"{prefix}.items[{i_index}]"
            if not isinstance(item, dict):
                f.add(ip, "Cada actividad debe ser un objeto.")
                continue
            time_value = item.get("time", "")
            if time_value and (not isinstance(time_value, str) or not TIME_RE.match(time_value)):
                f.add(f"{ip}.time", "Debe tener formato HH:MM.")
            clean_items.append(
                {
                    "time": time_value or "",
                    "title": v_text(f, item, "title", max_len=120) or "",
                    "place": v_text(f, item, "place", min_len=0, max_len=120, required=False, default="") or "",
                    "costCOP": v_int(f, item, "costCOP", lo=0, hi=MAX_MONEY, required=False, default=0) or 0,
                    "notes": v_text(f, item, "notes", min_len=0, max_len=300, required=False, default="") or "",
                }
            )
        clean_items.sort(key=lambda x: x["time"] or "99:99")
        clean_days.append({"date": date_value, "items": clean_items})
    f.raise_if_any()
    clean_days.sort(key=lambda d: d["date"])
    return clean_days


def _load_trip(sub: str, event: dict) -> tuple[str, dict]:
    trip_id = check_id(event["pathParameters"].get("id"), "Viaje")
    trip = repo.get_item(sub, f"TRIP#{trip_id}")
    if not trip:
        raise not_found("Viaje")
    return trip_id, trip


def get_itinerary(event, sub):
    trip_id, _ = _load_trip(sub, event)
    item = repo.get_item(sub, f"ITIN#{trip_id}")
    if not item:
        raise not_found("Itinerario")
    return response(200, repo.public(item) | {"tripId": trip_id})


def create_itinerary(event, sub):
    trip_id, trip = _load_trip(sub, event)
    days = _validate_days(parse_body(event), trip)
    item = {"PK": pk(sub), "SK": f"ITIN#{trip_id}", "tripId": trip_id, "days": days, "updatedAt": now_iso()}
    try:
        table().put_item(Item=item, ConditionExpression="attribute_not_exists(PK)")
    except ClientError as error:
        if error.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise conflict("ITINERARY_EXISTS", "El viaje ya tiene itinerario; usa la actualizacion.")
        raise
    return response(201, repo.public(item))


def update_itinerary(event, sub):
    trip_id, trip = _load_trip(sub, event)
    days = _validate_days(parse_body(event), trip)
    item = {"PK": pk(sub), "SK": f"ITIN#{trip_id}", "tripId": trip_id, "days": days, "updatedAt": now_iso()}
    # Reemplazo completo: el cliente (o el agente) envia el itinerario resultante.
    table().put_item(Item=item)
    return response(200, repo.public(item))


handler = make_handler(
    {
        "GET /trips/{id}/itinerary": get_itinerary,
        "POST /trips/{id}/itinerary": create_itinerary,
        "PUT /trips/{id}/itinerary": update_itinerary,
    }
)
