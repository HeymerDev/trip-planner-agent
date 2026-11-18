"""
Tools de negocio del Orchestrator: viajes, itinerarios, reservas, monedero, divisas y transporte.

Cada Tool es una operacion de negocio respaldada por una Lambda: llama a la API de TripPlanner
(API Gateway -> Lambda -> DynamoDB) reenviando el JWT del usuario. El agente decide QUE hacer;
la Lambda valida y ejecuta; y la identidad la fija el token, no el modelo.

Cada resultado correcto se publica tambien como evento de UI para que el frontend lo pinte.
"""

import json
import os
from typing import Any, Optional

import httpx
from strands import tool

import ui

API_URL = os.environ.get("API_URL", "").rstrip("/")
MAX_RESULT_CHARS = 8000


async def _api(method: str, path: str, *, body: dict | None = None, params: dict | None = None) -> tuple[int, Any]:
    if not API_URL:
        return 0, {"error": {"code": "NOT_CONFIGURED", "message": "La API de negocio no esta configurada."}}
    state = ui.current()
    if not state.token:
        return 401, {"error": {"code": "UNAUTHORIZED", "message": "No hay una sesion de usuario autenticada."}}
    try:
        async with httpx.AsyncClient(timeout=25) as client:
            response = await client.request(
                method,
                API_URL + path,
                json=body,
                params={k: v for k, v in (params or {}).items() if v},
                headers={"Authorization": f"Bearer {state.token}"},
            )
    except httpx.HTTPError:
        return 0, {"error": {"code": "UNREACHABLE", "message": "No se pudo contactar el servicio de negocio."}}
    try:
        return response.status_code, response.json()
    except ValueError:
        return response.status_code, {"error": {"code": "BAD_RESPONSE", "message": "Respuesta inesperada del servicio."}}


def _out(status: int, data: Any) -> str:
    """Resultado para el modelo: el JSON de la API (o el error con su mensaje y campos)."""
    text = json.dumps(data, ensure_ascii=False, default=str)
    return text if len(text) <= MAX_RESULT_CHARS else text[:MAX_RESULT_CHARS] + "...(recortado)"


def _ok(status: int) -> bool:
    return 200 <= status < 300


def _compact(**fields) -> dict:
    return {k: v for k, v in fields.items() if v is not None and v != ""}


# --------------------------------------------------------------------------------- viajes


@tool
async def create_trip(
    origin: str,
    destination: str,
    start_date: str,
    end_date: str,
    travelers: int,
    budget_cop: int,
    name: str = "",
    notes: str = "",
) -> str:
    """
    Crea un viaje del usuario (se guarda en la base de datos).

    Usala cuando el usuario pida crear/guardar/registrar un viaje. Si faltan datos obligatorios
    (origen, destino, fechas, numero de viajeros o presupuesto) pideselos antes de llamarla.

    Args:
        origin: Ciudad de origen, por ejemplo "Bogota".
        destination: Ciudad de destino, por ejemplo "Cartagena".
        start_date: Fecha de salida en formato AAAA-MM-DD.
        end_date: Fecha de regreso en formato AAAA-MM-DD (no anterior a la de salida).
        travelers: Numero total de viajeros (incluye al usuario), entre 1 y 20.
        budget_cop: Presupuesto total en pesos colombianos (entero).
        name: Nombre opcional del viaje.
        notes: Notas opcionales.

    Returns:
        JSON del viaje creado (con su "id") o un error con los campos invalidos.
    """
    status, data = await _api(
        "POST",
        "/trips",
        body=_compact(
            origin=origin, destination=destination, startDate=start_date, endDate=end_date,
            travelers=travelers, budgetCOP=budget_cop, name=name, notes=notes,
        ),
    )
    if _ok(status):
        ui.emit("trip", {"trip": data})
    return _out(status, data)


@tool
async def get_trips(trip_id: str = "") -> str:
    """
    Consulta los viajes del usuario. Sin trip_id lista todos; con trip_id devuelve el detalle
    del viaje con su itinerario, reservas y resumen de presupuesto.

    Args:
        trip_id: Id del viaje (opcional).

    Returns:
        JSON con los viajes o el detalle del viaje.
    """
    if not trip_id:
        status, data = await _api("GET", "/trips")
        if _ok(status):
            ui.emit("trips", {"trips": data["trips"]})
        return _out(status, data)

    status, data = await _api("GET", f"/trips/{trip_id}")
    if _ok(status):
        ui.emit("trip", {"trip": data["trip"], "budget": data["budget"]})
        if data.get("itinerary"):
            ui.emit("itinerary", {"tripId": trip_id, **data["itinerary"]})
        if data.get("reservations"):
            ui.emit("reservations", {"reservations": data["reservations"]})
    return _out(status, data)


@tool
async def update_trip(
    trip_id: str,
    name: Optional[str] = None,
    origin: Optional[str] = None,
    destination: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    travelers: Optional[int] = None,
    budget_cop: Optional[int] = None,
    notes: Optional[str] = None,
    status: Optional[str] = None,
) -> str:
    """
    Actualiza datos de un viaje existente. Envia solo los campos que cambian.

    Args:
        trip_id: Id del viaje a actualizar.
        name: Nuevo nombre.
        origin: Nuevo origen.
        destination: Nuevo destino.
        start_date: Nueva fecha de salida AAAA-MM-DD.
        end_date: Nueva fecha de regreso AAAA-MM-DD.
        travelers: Nuevo numero de viajeros.
        budget_cop: Nuevo presupuesto en COP.
        notes: Nuevas notas.
        status: Estado: PLANEADO, CONFIRMADO, FINALIZADO o CANCELADO.

    Returns:
        JSON del viaje actualizado o el error.
    """
    body = _compact(
        name=name, origin=origin, destination=destination, startDate=start_date, endDate=end_date,
        travelers=travelers, budgetCOP=budget_cop, notes=notes, status=status,
    )
    code, data = await _api("PATCH", f"/trips/{trip_id}", body=body)
    if _ok(code):
        ui.emit("trip", {"trip": data})
    return _out(code, data)


# ------------------------------------------------------------------------------ itinerario


@tool
async def create_itinerary(trip_id: str, days: list[dict[str, Any]]) -> str:
    """
    Crea el itinerario de un viaje (falla si ya tiene uno: en ese caso usa update_itinerary).

    Args:
        trip_id: Id del viaje.
        days: Lista de dias. Cada dia: {"date": "AAAA-MM-DD", "items": [{"time": "HH:MM",
            "title": "...", "place": "...", "costCOP": 0, "notes": "..."}]}. Las fechas deben
            estar dentro de las del viaje y cada actividad debe tener "title".

    Returns:
        JSON del itinerario guardado o el error.
    """
    status, data = await _api("POST", f"/trips/{trip_id}/itinerary", body={"days": days})
    if _ok(status):
        ui.emit("itinerary", {"tripId": trip_id, **data})
    return _out(status, data)


@tool
async def update_itinerary(trip_id: str, days: list[dict[str, Any]]) -> str:
    """
    Modifica el itinerario de un viaje reemplazandolo por el que envias. Para cambiar una
    actividad, consulta antes el itinerario con get_trips y envia la lista de dias completa.

    Args:
        trip_id: Id del viaje.
        days: Lista COMPLETA de dias resultante (mismo formato que create_itinerary).

    Returns:
        JSON del itinerario guardado o el error.
    """
    status, data = await _api("PUT", f"/trips/{trip_id}/itinerary", body={"days": days})
    if _ok(status):
        ui.emit("itinerary", {"tripId": trip_id, **data})
    return _out(status, data)


# --------------------------------------------------------------------------------- reservas


@tool
async def create_reservation(
    trip_id: str,
    kind: str,
    title: str,
    price_cop: int,
    pay: bool = False,
    details: Optional[dict[str, Any]] = None,
    link: str = "",
    idempotency_key: str = "",
    original_price: Optional[float] = None,
    original_currency: str = "",
    fx_rate: Optional[float] = None,
) -> str:
    """
    Registra una reserva SIMULADA de un vuelo, hotel o actividad asociada a un viaje.

    Con pay=False solo registra la reserva. Con pay=True hace ademas la COMPRA SIMULADA: descuenta
    el precio del saldo del monedero del usuario de forma atomica. Usa pay=True UNICAMENTE si el
    usuario confirmo explicitamente que quiere comprar. Si el saldo no alcanza, el error lo indica
    y debes ofrecer recargar el monedero (top_up_wallet) con el permiso del usuario.

    Args:
        trip_id: Id del viaje al que se asocia (debe existir; crealo antes con create_trip).
        kind: FLIGHT, HOTEL o ACTIVITY.
        title: Titulo corto, por ejemplo "BOG -> CTG · LATAM 19:40".
        price_cop: Precio TOTAL en pesos colombianos (entero). Convierte con convert_currency si el precio viene en USD.
        pay: True para cobrar del monedero.
        details: Datos libres de la reserva (aerolinea, horarios, direccion, fechas...).
        link: URL de compra/reserva del proveedor, copiada tal cual.
        idempotency_key: Clave unica de esta compra para evitar cobros dobles al reintentar.
        original_price: Precio en la moneda original (opcional).
        original_currency: Moneda original, por ejemplo USD (opcional).
        fx_rate: Tasa usada para convertir a COP (opcional).

    Returns:
        JSON de la reserva creada (y el saldo si hubo compra) o el error.
    """
    if link and not ui.known_link(link):
        link = ""  # solo se guardan enlaces que entrego un especialista; nunca inventados por el modelo
    body = _compact(
        tripId=trip_id, kind=kind, title=title, priceCOP=price_cop, details=details or {}, link=link,
        originalPrice=original_price, originalCurrency=original_currency, fxRate=fx_rate,
    )
    if pay:
        gate = ui.purchase_gate(trip_id, price_cop)
        if gate:
            return gate  # nada se cobra hasta que el usuario confirme en un turno posterior
        if idempotency_key:
            body["idempotencyKey"] = idempotency_key
        status, data = await _api("POST", "/purchases", body=body)
        if _ok(status):
            ui.emit("reservation", {"reservation": data["reservation"], "balanceCOP": data["balanceCOP"]})
        return _out(status, data)
    status, data = await _api("POST", "/reservations", body=body)
    if _ok(status):
        ui.emit("reservation", {"reservation": data})
    return _out(status, data)


@tool
async def get_reservations(trip_id: str = "", status: str = "") -> str:
    """
    Consulta las reservas del usuario, opcionalmente filtradas por viaje o estado.

    Args:
        trip_id: Id del viaje (opcional).
        status: SIMULADA, PENDIENTE, CONFIRMADA o CANCELADA (opcional).

    Returns:
        JSON con la lista de reservas.
    """
    code, data = await _api("GET", "/reservations", params={"tripId": trip_id, "status": status})
    if _ok(code):
        ui.emit("reservations", {"reservations": data["reservations"]})
    return _out(code, data)


@tool
async def update_reservation(
    reservation_id: str,
    status: Optional[str] = None,
    trip_id: Optional[str] = None,
    title: Optional[str] = None,
    link: Optional[str] = None,
) -> str:
    """
    Actualiza una reserva: cambia su estado, la asocia a otro viaje o edita su titulo/enlace.

    El estado puede ser SIMULADA, PENDIENTE o CANCELADA (CONFIRMADA solo la fija un proveedor real).
    Cancelar una reserva pagada con el monedero devuelve el dinero al saldo, una sola vez.

    Args:
        reservation_id: Id de la reserva.
        status: Nuevo estado (opcional).
        trip_id: Id del viaje al que se reasocia (opcional).
        title: Nuevo titulo (opcional).
        link: Nuevo enlace (opcional).

    Returns:
        JSON de la reserva actualizada o el error.
    """
    body = _compact(status=status, tripId=trip_id, title=title, link=link)
    code, data = await _api("PATCH", f"/reservations/{reservation_id}", body=body)
    if _ok(code):
        ui.emit("reservation", {"reservation": data})
    return _out(code, data)


# -------------------------------------------------------------------------------- monedero


@tool
async def get_wallet() -> str:
    """
    Consulta el saldo del monedero simulado del usuario (en COP) y sus ultimos movimientos.

    Returns:
        JSON con el saldo y el historial.
    """
    status, data = await _api("GET", "/wallet")
    if _ok(status):
        ui.emit("wallet", data)
    return _out(status, data)


@tool
async def top_up_wallet(amount_cop: int) -> str:
    """
    Recarga el monedero SIMULADO del usuario. No pide ni guarda datos de tarjeta: solo suma un monto.
    Hazlo unicamente si el usuario lo pidio o acepto expresamente el monto.

    Args:
        amount_cop: Monto en pesos colombianos, entre 1.000 y 10.000.000.

    Returns:
        JSON con el nuevo saldo o el error.
    """
    if not ui.topup_allowed():
        return json.dumps(
            {"status": "NOT_REQUESTED", "message": "El usuario no pidio recargar el monedero. Preguntale si quiere recargar y cuanto."},
            ensure_ascii=False,
        )
    status, data = await _api("POST", "/wallet/topup", body={"amountCOP": amount_cop})
    if _ok(status):
        ui.emit("wallet", data)
    return _out(status, data)


# ------------------------------------------------------------------------------ extras


@tool
async def convert_currency(amount: float, from_currency: str, to_currency: str = "COP") -> str:
    """
    Convierte un monto entre monedas con la tasa de cambio actual (por ejemplo USD a COP).
    Usala para dar precios de vuelos u hoteles en pesos y para llenar price_cop de una reserva.

    Args:
        amount: Monto a convertir.
        from_currency: Moneda de origen (codigo de 3 letras, por ejemplo USD).
        to_currency: Moneda de destino (por defecto COP).

    Returns:
        JSON con tasa, resultado, fecha de la tasa y fuente.
    """
    status, data = await _api(
        "GET", "/fx", params={"from": from_currency, "to": to_currency, "amount": str(amount)}
    )
    if _ok(status):
        ui.emit("currency", data)
    return _out(status, data)


@tool
async def compare_transport(origin: str, destination: str) -> str:
    """
    Compara viajar en bus o en avion entre dos ciudades (tiempo puerta a puerta y costo estimado
    del bus) y recomienda una opcion. Util para trayectos cortos, donde el bus puede convenir mas.
    Los datos de bus son estimaciones: dilo al usuario.

    Args:
        origin: Ciudad de origen.
        destination: Ciudad de destino.

    Returns:
        JSON con la recomendacion, tiempos, costos estimados y supuestos.
    """
    status, data = await _api("GET", "/transport", params={"origin": origin, "destination": destination})
    if _ok(status):
        ui.emit("transport", data)
    return _out(status, data)


BUSINESS_TOOLS = [
    create_trip,
    get_trips,
    update_trip,
    create_itinerary,
    update_itinerary,
    create_reservation,
    get_reservations,
    update_reservation,
    get_wallet,
    top_up_wallet,
    convert_currency,
    compare_transport,
]
