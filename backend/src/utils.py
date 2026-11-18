"""
Lambda `utils`: servicios auxiliares de viaje (Tools convert_currency y compare_transport).

- GET /fx?from=USD&to=COP&amount=100  -> tasa de cambio actual (open.er-api.com, sin clave).
- GET /transport?origin=Bogota&destination=Medellin -> compara bus y avion puerta a puerta.

Los datos de bus son ESTIMACIONES (no hay una API abierta de buses): la respuesta lo declara.
"""

import json
import math
import re
import time
import urllib.parse
import urllib.request

from common import ApiError, make_handler, response

FX_URL = "https://open.er-api.com/v6/latest/{base}"
GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search?name={name}&count=1&language=es&format=json"
CURRENCY_RE = re.compile(r"^[A-Z]{3}$")
_cache: dict[str, tuple[float, dict]] = {}
CACHE_SECONDS = 3600

# Supuestos del comparador (documentados en docs/sdd/design.md)
ROAD_FACTOR = 1.35  # la carretera es ~35% mas larga que la linea recta (cordilleras)
BUS_KMH = 55  # velocidad media de bus intermunicipal en Colombia
BUS_COP_PER_KM = 250  # tarifa estimada
AIR_KMH = 750  # velocidad media de crucero incluyendo ascenso/descenso
AIRPORT_OVERHEAD_H = 3.0  # traslados + llegada anticipada + equipaje


def _get_json(url: str) -> dict:
    cached = _cache.get(url)
    if cached and time.time() - cached[0] < CACHE_SECONDS:
        return cached[1]
    request = urllib.request.Request(url, headers={"User-Agent": "tripplanner-ai/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001 - se traduce a un error de servicio externo
        raise ApiError(502, "UPSTREAM_ERROR", "El servicio externo no esta disponible en este momento.") from exc
    _cache[url] = (time.time(), data)
    return data


def fx(event, sub):
    params = event.get("queryStringParameters") or {}
    base = (params.get("from") or "").upper()
    quote = (params.get("to") or "").upper()
    fields = {}
    if not CURRENCY_RE.match(base):
        fields["from"] = "Debe ser un codigo de moneda de 3 letras (ej. USD)."
    if not CURRENCY_RE.match(quote):
        fields["to"] = "Debe ser un codigo de moneda de 3 letras (ej. COP)."
    amount = 1.0
    if params.get("amount") is not None:
        try:
            amount = float(params["amount"])
            if not 0 <= amount <= 1e12:
                raise ValueError
        except ValueError:
            fields["amount"] = "Debe ser un numero entre 0 y 1.000.000.000.000."
    if fields:
        raise ApiError(400, "VALIDATION_ERROR", "Parametros invalidos.", fields)

    data = _get_json(FX_URL.format(base=base))
    rate = (data.get("rates") or {}).get(quote)
    if data.get("result") != "success" or rate is None:
        raise ApiError(400, "UNSUPPORTED_CURRENCY", f"No hay tasa disponible para {base} -> {quote}.")
    return response(
        200,
        {
            "from": base,
            "to": quote,
            "rate": rate,
            "amount": amount,
            "result": round(amount * rate, 2),
            "asOf": data.get("time_last_update_utc"),
            "source": "open.er-api.com",
        },
    )


def _geocode(name: str) -> tuple[str, float, float]:
    data = _get_json(GEOCODE_URL.format(name=urllib.parse.quote(name)))
    results = data.get("results") or []
    if not results:
        raise ApiError(404, "PLACE_NOT_FOUND", f"No se encontro la ciudad '{name}'.")
    top = results[0]
    return f"{top['name']}, {top.get('country', '')}".strip(", "), top["latitude"], top["longitude"]


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi, dlmb = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def compare(distance_km: float) -> dict:
    """Compara bus y avion puerta a puerta para una distancia en linea recta."""
    road_km = distance_km * ROAD_FACTOR
    bus_h = road_km / BUS_KMH
    flight_h = distance_km / AIR_KMH + AIRPORT_OVERHEAD_H
    bus_cost = int(round(road_km * BUS_COP_PER_KM, -3))

    if bus_h <= flight_h * 1.15:
        choice = "BUS"
        reason = (
            f"En {round(distance_km)} km el bus ({bus_h:.1f} h) tarda lo mismo o menos que el avion puerta a puerta "
            f"({flight_h:.1f} h, incluyendo traslados y filas) y suele costar menos."
        )
    else:
        choice = "AVION"
        reason = (
            f"En {round(distance_km)} km el avion ({flight_h:.1f} h puerta a puerta) ahorra "
            f"{bus_h - flight_h:.1f} h frente al bus ({bus_h:.1f} h)."
        )
    return {
        "recommendation": choice,
        "reason": reason,
        "distanceKm": round(distance_km),
        "bus": {"hours": round(bus_h, 1), "estimatedCostCOP": bus_cost, "isEstimate": True},
        "flight": {"hours": round(flight_h, 1), "airHours": round(distance_km / AIR_KMH, 1), "isEstimate": True},
        "assumptions": (
            f"Estimaciones: carretera = {ROAD_FACTOR}x la linea recta, bus a {BUS_KMH} km/h, tarifa de "
            f"{BUS_COP_PER_KM} COP/km, avion a {AIR_KMH} km/h mas {AIRPORT_OVERHEAD_H:g} h de traslados y filas. "
            "Consulta el precio real del vuelo con el agente de vuelos."
        ),
    }


def transport(event, sub):
    params = event.get("queryStringParameters") or {}
    origin, destination = (params.get("origin") or "").strip(), (params.get("destination") or "").strip()
    fields = {}
    for name, value in (("origin", origin), ("destination", destination)):
        if not 2 <= len(value) <= 80:
            fields[name] = "Debe tener entre 2 y 80 caracteres."
    if fields:
        raise ApiError(400, "VALIDATION_ERROR", "Parametros invalidos.", fields)

    o_name, o_lat, o_lon = _geocode(origin)
    d_name, d_lat, d_lon = _geocode(destination)
    result = compare(haversine_km(o_lat, o_lon, d_lat, d_lon))
    return response(200, {"origin": o_name, "destination": d_name, **result})


handler = make_handler({"GET /fx": fx, "GET /transport": transport})
