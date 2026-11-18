"""Lambda `profile`: perfil, preferencias y dashboard del usuario."""

from datetime import date

from botocore.exceptions import ClientError

import repo
from common import (
    ApiError,
    Fields,
    MAX_MONEY,
    make_handler,
    now_iso,
    parse_body,
    pk,
    response,
    strip_keys,
    table,
    user_email,
    v_int,
    v_text,
)

ACTIVITY_OPTIONS = {"cultura", "playa", "gastronomia", "aventura", "naturaleza", "nocturna", "compras", "relax"}


def _ensure_profile(event: dict, sub: str) -> dict:
    """Crea el perfil en el primer acceso (idempotente) y lo devuelve."""
    existing = repo.get_item(sub, "PROFILE")
    if existing:
        return existing
    item = {
        "PK": pk(sub),
        "SK": "PROFILE",
        "email": user_email(event) or "",
        "name": "",
        "createdAt": now_iso(),
    }
    try:
        table().put_item(Item=item, ConditionExpression="attribute_not_exists(PK)")
    except ClientError as error:
        if error.response["Error"]["Code"] != "ConditionalCheckFailedException":
            raise
        return repo.get_item(sub, "PROFILE") or item
    return item


def get_me(event, sub):
    profile = _ensure_profile(event, sub)
    return response(200, {"id": sub, **strip_keys(profile)})


def put_me(event, sub):
    _ensure_profile(event, sub)
    data = parse_body(event)
    f = Fields()
    name = v_text(f, data, "name", max_len=80, required=False)
    email = v_text(f, data, "email", max_len=120, required=False)
    if email and "@" not in email:
        f.add("email", "Debe ser un correo valido.")
    f.raise_if_any()

    sets, values = [], {}
    if name is not None:
        sets.append("#n = :n")
        values[":n"] = name
    if email is not None:
        sets.append("email = :e")
        values[":e"] = email
    if sets:
        table().update_item(
            Key={"PK": pk(sub), "SK": "PROFILE"},
            UpdateExpression="SET " + ", ".join(sets),
            ExpressionAttributeValues=values,
            **({"ExpressionAttributeNames": {"#n": "name"}} if name is not None else {}),
        )
    return get_me(event, sub)


def _prefs_view(item: dict | None) -> dict:
    if not item:
        return {"defaultBudgetCOP": None, "activities": [], "airlines": [], "restrictions": ""}
    return strip_keys(item)


def get_preferences(event, sub):
    return response(200, _prefs_view(repo.get_item(sub, "PREFS")))


def put_preferences(event, sub):
    data = parse_body(event)
    f = Fields()
    budget = v_int(f, data, "defaultBudgetCOP", lo=0, hi=MAX_MONEY, required=False)
    restrictions = v_text(f, data, "restrictions", min_len=0, max_len=300, required=False, default="")

    activities = data.get("activities", [])
    airlines = data.get("airlines", [])
    if not isinstance(activities, list) or len(activities) > 8 or any(a not in ACTIVITY_OPTIONS for a in activities):
        f.add("activities", f"Lista de hasta 8 valores entre: {', '.join(sorted(ACTIVITY_OPTIONS))}.")
    if not isinstance(airlines, list) or len(airlines) > 10 or any(
        not isinstance(a, str) or not 1 <= len(a) <= 40 for a in airlines
    ):
        f.add("airlines", "Lista de hasta 10 nombres de aerolinea.")
    f.raise_if_any()

    item = {
        "PK": pk(sub),
        "SK": "PREFS",
        "defaultBudgetCOP": budget,
        "activities": activities,
        "airlines": airlines,
        "restrictions": restrictions or "",
        "updatedAt": now_iso(),
    }
    table().put_item(Item=item)
    return response(200, _prefs_view(item))


def dashboard(event, sub):
    today = date.today().isoformat()
    trips = [repo.trip_view(i) for i in repo.query_prefix(sub, "TRIP#")]
    reservations = [repo.reservation_view(i) for i in repo.query_prefix(sub, "RES#")]

    upcoming = sorted((t for t in trips if t["endDate"] >= today), key=lambda t: t["startDate"])[:5]
    recent = sorted(reservations, key=lambda r: r["createdAt"], reverse=True)[:5]
    active_res = [r for r in reservations if r["status"] != "CANCELADA"]
    return response(
        200,
        {
            "upcomingTrips": upcoming,
            "recentReservations": recent,
            "walletBalanceCOP": repo.wallet_balance(sub),
            "counts": {"trips": len(trips), "reservations": len(active_res)},
            "totalReservedCOP": sum(int(r.get("priceCOP", 0)) for r in active_res),
        },
    )


handler = make_handler(
    {
        "GET /me": get_me,
        "PUT /me": put_me,
        "GET /me/preferences": get_preferences,
        "PUT /me/preferences": put_preferences,
        "GET /dashboard": dashboard,
    }
)
