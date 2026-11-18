"""
Codigo comun de las Lambdas de TripPlanner: respuestas HTTP, errores, validacion,
acceso a DynamoDB y un enrutador minimo por `routeKey` de API Gateway (HTTP API v2).

Regla de seguridad central: la identidad del usuario SIEMPRE sale del JWT que ya
verifico API Gateway (`requestContext.authorizer.jwt.claims.sub`). Ningun dato del
cuerpo, de la ruta ni del modelo de lenguaje puede cambiar a que usuario se accede.
"""

import base64
import hashlib
import json
import logging
import os
import re
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Callable

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

TABLE_NAME = os.environ.get("TABLE_NAME", "tripplanner-main")
MAX_BODY_BYTES = 64 * 1024

_dynamodb = None


def table():
    """Tabla unica (reutilizada entre invocaciones calientes)."""
    global _dynamodb
    if _dynamodb is None:
        _dynamodb = boto3.resource("dynamodb")
    return _dynamodb.Table(TABLE_NAME)


def client():
    """Cliente de bajo nivel (necesario para TransactWriteItems con ConditionExpression)."""
    return boto3.client("dynamodb")


# ----------------------------------------------------------------------------- errores


class ApiError(Exception):
    """Error de negocio con codigo HTTP y mensaje apto para el usuario."""

    def __init__(self, status: int, code: str, message: str, fields: dict | None = None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.fields = fields


def not_found(what: str = "Recurso") -> ApiError:
    return ApiError(404, "NOT_FOUND", f"{what} no encontrado.")


def conflict(code: str, message: str) -> ApiError:
    return ApiError(409, code, message)


# --------------------------------------------------------------------------- respuestas


def _json_default(value: Any):
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, set):
        return sorted(value)
    raise TypeError(f"No serializable: {type(value)}")


def response(status: int, body: Any = None) -> dict:
    result = {
        "statusCode": status,
        "headers": {"Content-Type": "application/json", "Cache-Control": "no-store"},
    }
    if body is not None:
        result["body"] = json.dumps(body, default=_json_default, ensure_ascii=False)
    return result


def error_response(error: ApiError) -> dict:
    payload: dict[str, Any] = {"code": error.code, "message": error.message}
    if error.fields:
        payload["fields"] = error.fields
    return response(error.status, {"error": payload})


# --------------------------------------------------------------------------- entrada


def user_sub(event: dict) -> str:
    """Identidad verificada del usuario (claim `sub` del JWT validado por API Gateway)."""
    try:
        sub = event["requestContext"]["authorizer"]["jwt"]["claims"]["sub"]
    except (KeyError, TypeError):
        sub = None
    if not sub or not isinstance(sub, str):
        raise ApiError(401, "UNAUTHORIZED", "Sesion no valida.")
    return sub


def user_email(event: dict) -> str | None:
    claims = (event.get("requestContext", {}).get("authorizer", {}) or {}).get("jwt", {}).get("claims", {}) or {}
    return claims.get("email") or claims.get("username")


def pk(sub: str) -> str:
    return f"USER#{sub}"


def parse_body(event: dict) -> dict:
    raw = event.get("body")
    if raw is None or raw == "":
        return {}
    if event.get("isBase64Encoded"):
        raw = base64.b64decode(raw).decode("utf-8", errors="replace")
    if len(raw.encode("utf-8")) > MAX_BODY_BYTES:
        raise ApiError(413, "PAYLOAD_TOO_LARGE", "El cuerpo de la peticion es demasiado grande.")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        raise ApiError(400, "INVALID_JSON", "El cuerpo debe ser JSON valido.")
    if not isinstance(data, dict):
        raise ApiError(400, "INVALID_JSON", "El cuerpo debe ser un objeto JSON.")
    return data


# ------------------------------------------------------------------------- validacion

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
ID_RE = re.compile(r"^[A-Za-z0-9_-]{6,64}$")
MAX_MONEY = 1_000_000_000


class Fields:
    """Acumula errores por campo y los lanza juntos (un 400 con la lista completa)."""

    def __init__(self):
        self.errors: dict[str, str] = {}

    def add(self, name: str, message: str):
        self.errors.setdefault(name, message)

    def raise_if_any(self):
        if self.errors:
            raise ApiError(400, "VALIDATION_ERROR", "Hay datos invalidos en la peticion.", self.errors)


def v_text(f: Fields, data: dict, name: str, *, min_len=1, max_len=120, required=True, default=None):
    value = data.get(name)
    if value is None:
        if required:
            f.add(name, "Es obligatorio.")
        return default
    if not isinstance(value, str):
        f.add(name, "Debe ser texto.")
        return default
    value = value.strip()
    if len(value) < min_len or len(value) > max_len:
        f.add(name, f"Debe tener entre {min_len} y {max_len} caracteres.")
        return default
    return value


def v_int(f: Fields, data: dict, name: str, *, lo: int, hi: int, required=True, default=None):
    value = data.get(name)
    if value is None:
        if required:
            f.add(name, "Es obligatorio.")
        return default
    # bool es subclase de int: se rechaza explicitamente.
    if isinstance(value, bool) or not isinstance(value, (int, float)) or int(value) != value:
        f.add(name, "Debe ser un numero entero.")
        return default
    value = int(value)
    if value < lo or value > hi:
        f.add(name, f"Debe estar entre {lo} y {hi}.")
        return default
    return value


def v_date(f: Fields, data: dict, name: str, *, required=True, default=None) -> str | None:
    value = data.get(name)
    if value is None:
        if required:
            f.add(name, "Es obligatoria.")
        return default
    if not isinstance(value, str) or not DATE_RE.match(value):
        f.add(name, "Debe tener formato AAAA-MM-DD.")
        return default
    try:
        date.fromisoformat(value)
    except ValueError:
        f.add(name, "No es una fecha valida.")
        return default
    return value


def v_enum(f: Fields, data: dict, name: str, allowed: set[str], *, required=True, default=None):
    value = data.get(name)
    if value is None:
        if required:
            f.add(name, "Es obligatorio.")
        return default
    if value not in allowed:
        f.add(name, f"Debe ser uno de: {', '.join(sorted(allowed))}.")
        return default
    return value


def v_url(f: Fields, data: dict, name: str, *, required=False):
    value = data.get(name)
    if value is None or value == "":
        if required:
            f.add(name, "Es obligatorio.")
        return None
    if not isinstance(value, str) or len(value) > 2000 or not re.match(r"^https?://", value):
        f.add(name, "Debe ser una URL http(s) de hasta 2000 caracteres.")
        return None
    return value


def check_date_range(f: Fields, start: str | None, end: str | None, *, max_days: int = 90):
    if start and end:
        d0, d1 = date.fromisoformat(start), date.fromisoformat(end)
        if d1 < d0:
            f.add("endDate", "No puede ser anterior a la fecha de inicio.")
        elif (d1 - d0).days + 1 > max_days:
            f.add("endDate", f"El viaje no puede durar mas de {max_days} dias.")


def sanitize_json(value: Any, *, depth: int = 0, max_depth: int = 4, max_items: int = 50) -> Any:
    """Copia acotada de un objeto JSON libre (details): limita profundidad, tamano y tipos."""
    if depth > max_depth:
        return None
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    if isinstance(value, str):
        return value[:500]
    if isinstance(value, list):
        return [sanitize_json(v, depth=depth + 1) for v in value[:max_items]]
    if isinstance(value, dict):
        return {str(k)[:60]: sanitize_json(v, depth=depth + 1) for k, v in list(value.items())[:max_items]}
    return None


# ----------------------------------------------------------------------------- utilidades


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def new_id() -> str:
    return uuid.uuid4().hex[:16]


def derive_id(sub: str, key: str) -> str:
    """Id determinista a partir de una clave de idempotencia (acotada al usuario)."""
    return hashlib.sha256(f"{sub}:{key}".encode()).hexdigest()[:16]


def check_id(value: str | None, what: str = "Recurso") -> str:
    if not value or not ID_RE.match(value):
        raise not_found(what)
    return value


def strip_keys(item: dict | None) -> dict | None:
    """Quita PK/SK internas antes de devolver un item al cliente."""
    if item is None:
        return None
    return {k: v for k, v in item.items() if k not in ("PK", "SK")}


# ------------------------------------------------------------------------------ enrutador


def make_handler(routes: dict[str, Callable[[dict, str], dict]]):
    """
    Crea el handler de Lambda para un diccionario `routeKey -> funcion(event, sub)`.
    Cualquier excepcion no controlada se registra y se devuelve como 500 generico.
    """

    def handler(event, context):
        route_key = event.get("routeKey", "")
        try:
            func = routes.get(route_key)
            if func is None:
                raise ApiError(404, "NOT_FOUND", "Ruta no encontrada.")
            sub = user_sub(event)
            return func(event, sub)
        except ApiError as error:
            if error.status >= 500:
                logger.error("ApiError %s %s", route_key, error.message)
            return error_response(error)
        except Exception:  # noqa: BLE001 - ultima barrera: nunca filtrar detalles internos
            logger.exception("Error no controlado en %s", route_key)
            return error_response(ApiError(500, "INTERNAL_ERROR", "Ocurrio un error interno. Intenta de nuevo."))

    return handler


# --------------------------------------------------------------------------- transacciones


def transact(items: list[dict]) -> None:
    """
    TransactWriteItems con tipos nativos de Python (el cliente `meta.client` del recurso
    serializa Decimal/str/bool). Cada item usa 'TableName' explicito.
    """
    for entry in items:
        for op in entry.values():
            op["TableName"] = TABLE_NAME
    table().meta.client.transact_write_items(TransactItems=items)


def cancellation_codes(error) -> list[str]:
    """Codigos por operacion de una TransactionCanceledException ('None' = la operacion estaba bien)."""
    reasons = error.response.get("CancellationReasons") or []
    return [r.get("Code", "None") for r in reasons]
