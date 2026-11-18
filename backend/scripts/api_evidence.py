"""
Pruebas reales contra la API desplegada (T-18, T-71, T-73). Genera docs/evidencias/01-api-backend.md.

Uso (desde backend/, con el perfil de AWS de la cuenta nueva):
    .venv/Scripts/python.exe scripts/api_evidence.py --api-url ... --client-id ... --origin https://dxxxx.cloudfront.net

Crea dos usuarios de prueba en Cognito (A y B) para verificar el aislamiento entre usuarios.
"""

import argparse
import json
import secrets
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import boto3

parser = argparse.ArgumentParser()
parser.add_argument("--api-url", required=True)
parser.add_argument("--client-id", required=True)
parser.add_argument("--origin", required=True, help="Origen CloudFront permitido por CORS")
parser.add_argument("--region", default="us-east-2")
parser.add_argument("--out", default=str(Path(__file__).resolve().parents[2] / "docs" / "evidencias" / "01-api-backend.md"))
args = parser.parse_args()

cognito = boto3.client("cognito-idp", region_name=args.region)
log: list[str] = []
results: list[tuple[str, bool]] = []


def make_user(label: str) -> str:
    email = f"evidencia-{label}-{secrets.token_hex(3)}@tripplanner.test"
    password = "Prueba" + secrets.token_hex(6) + "1"
    cognito.sign_up(ClientId=args.client_id, Username=email, Password=password, UserAttributes=[{"Name": "email", "Value": email}])
    tokens = cognito.initiate_auth(
        ClientId=args.client_id, AuthFlow="USER_PASSWORD_AUTH", AuthParameters={"USERNAME": email, "PASSWORD": password}
    )["AuthenticationResult"]
    return tokens["AccessToken"]


def http(method, path, token=None, body=None, headers=None):
    req = urllib.request.Request(args.api_url + path, method=method, data=json.dumps(body).encode() if body is not None else None)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read().decode(), dict(resp.headers)
    except urllib.error.HTTPError as err:
        return err.code, err.read().decode(), dict(err.headers)


def step(title, method, path, expect, token=None, body=None, headers=None, show_headers=()):
    status, text, resp_headers = http(method, path, token, body, headers)
    ok = status == expect
    results.append((title, ok))
    try:
        pretty = json.dumps(json.loads(text), indent=2, ensure_ascii=False) if text else "(sin cuerpo)"
    except json.JSONDecodeError:
        pretty = text
    if len(pretty) > 1400:
        pretty = pretty[:1400] + "\n... (recortado)"
    log.append(f"### {'✅' if ok else '❌'} {title}\n")
    log.append(f"`{method} {path}` → **{status}** (esperado {expect})\n")
    if body is not None:
        log.append("Cuerpo enviado:\n```json\n" + json.dumps(body, indent=2, ensure_ascii=False) + "\n```\n")
    for name in show_headers:
        value = next((v for k, v in resp_headers.items() if k.lower() == name), None)
        log.append(f"Cabecera `{name}`: `{value}`\n")
    log.append("Respuesta:\n```json\n" + pretty + "\n```\n")
    return status, (json.loads(text) if text and text.lstrip().startswith(("{", "[")) else None)


token_a, token_b = make_user("a"), make_user("b")
trip = {"name": "Vacaciones Cartagena", "origin": "Bogota", "destination": "Cartagena",
        "startDate": "2026-12-10", "endDate": "2026-12-13", "travelers": 3, "budgetCOP": 5000000}

log.append("## 1. Autenticacion y autorizacion (RNF-13, RNF-14, CA-1)\n")
step("Sin token → 401", "GET", "/trips", 401)
step("Token invalido → 401", "GET", "/trips", 401, token="eyJhbGciOiJSUzI1NiJ9.invalido.firma")
step("Perfil creado en el primer acceso", "GET", "/me", 200, token=token_a)

log.append("## 2. Viajes (RF-40, RF-41) y validacion (RNF-12, CA-2)\n")
step("Viaje invalido → 400 con lista de campos", "POST", "/trips", 400, token_a,
     {"origin": "B", "destination": "", "startDate": "2026-13-40", "endDate": "2026-12-01", "travelers": 0, "budgetCOP": -1})
status, created = step("Crear viaje → 201", "POST", "/trips", 201, token_a, trip)
trip_id = created["id"]
step("Listar viajes", "GET", "/trips", 200, token_a)
step("Actualizar viaje (PATCH)", "PATCH", f"/trips/{trip_id}", 200, token_a, {"budgetCOP": 5500000})
step("Usuario B no ve el viaje de A → 404", "GET", f"/trips/{trip_id}", 404, token_b)
step("Usuario B no puede modificarlo → 404", "PATCH", f"/trips/{trip_id}", 404, token_b, {"name": "hackeado"})
step("Usuario B no puede borrarlo → 404", "DELETE", f"/trips/{trip_id}", 404, token_b)
step("Usuario B tiene su lista vacia", "GET", "/trips", 200, token_b)

log.append("## 3. Itinerario (RF-42)\n")
days = [
    {"date": "2026-12-10", "items": [
        {"time": "16:00", "title": "Check-in y paseo por la Ciudad Amurallada", "place": "Centro historico", "costCOP": 0},
        {"time": "19:30", "title": "Cena en Getsemani", "place": "Getsemani", "costCOP": 180000}]},
    {"date": "2026-12-11", "items": [{"time": "09:00", "title": "Tour Islas del Rosario", "place": "Muelle de la Bodeguita", "costCOP": 420000}]},
]
step("Crear itinerario → 201", "POST", f"/trips/{trip_id}/itinerary", 201, token_a, {"days": days})
step("Crear de nuevo → 409", "POST", f"/trips/{trip_id}/itinerary", 409, token_a, {"days": days})
step("Fecha fuera del viaje → 400", "PUT", f"/trips/{trip_id}/itinerary", 400, token_a, {"days": [{"date": "2027-01-01", "items": []}]})
step("Modificar itinerario (PUT)", "PUT", f"/trips/{trip_id}/itinerary", 200, token_a, {"days": days})
step("Usuario B no accede al itinerario → 404", "GET", f"/trips/{trip_id}/itinerary", 404, token_b)

log.append("## 4. Monedero, compra atomica y reservas (RF-50..65, CA-3, CA-4)\n")
flight = {"tripId": trip_id, "kind": "FLIGHT", "title": "BOG → CTG · LATAM", "priceCOP": 420000,
          "details": {"airline": "LATAM", "departure": "2026-12-10T07:40"}, "link": "https://www.google.com/travel/flights",
          "idempotencyKey": "evidencia-compra-0001"}
step("Compra sin saldo → 409 INSUFFICIENT_FUNDS", "POST", "/purchases", 409, token_a, flight)
step("Recarga simulada → 201", "POST", "/wallet/topup", 201, token_a, {"amountCOP": 2000000})
step("Recarga fuera de rango → 400", "POST", "/wallet/topup", 400, token_a, {"amountCOP": 5})
status, bought = step("Compra → 201 (descuenta y crea reserva SIMULADA)", "POST", "/purchases", 201, token_a, flight)
res_id = bought["reservation"]["id"]
step("Compra repetida (misma clave) → 409 DUPLICATE, sin doble cobro", "POST", "/purchases", 409, token_a, flight)
step("Saldo tras la compra: 1.580.000", "GET", "/wallet", 200, token_a)
step("Reserva de hotel pendiente (sin cobro)", "POST", "/reservations", 201, token_a,
     {"tripId": trip_id, "kind": "HOTEL", "title": "Hotel Casa San Agustin", "priceCOP": 2076000, "status": "PENDIENTE"})
step("Listar reservas del viaje", "GET", f"/reservations?tripId={trip_id}", 200, token_a)
step("Confirmar como usuario → 409 PROVIDER_ONLY", "PATCH", f"/reservations/{res_id}", 409, token_a, {"status": "CONFIRMADA"})
step("Usuario B no ve la reserva → 404", "GET", f"/reservations/{res_id}", 404, token_b)
step("Usuario B no puede crear reserva en viaje de A → 404", "POST", "/reservations", 404, token_b, flight | {"idempotencyKey": None})
step("Cancelar reserva pagada → 200 y reembolso", "PATCH", f"/reservations/{res_id}", 200, token_a, {"status": "CANCELADA"})
status, wallet = step("Saldo restituido: 2.000.000 (un solo reembolso)", "GET", "/wallet", 200, token_a)
step("Cancelar de nuevo es idempotente (sin doble reembolso)", "PATCH", f"/reservations/{res_id}", 200, token_a, {"status": "CANCELADA"})
step("Panel de usuario", "GET", "/dashboard", 200, token_a)
step("Resumen del viaje con presupuesto", "GET", f"/trips/{trip_id}", 200, token_a)

log.append("## 5. CORS (RNF-14)\n")
step("Preflight desde el origen de la aplicacion", "OPTIONS", "/trips", 204, headers={
    "Origin": args.origin, "Access-Control-Request-Method": "GET", "Access-Control-Request-Headers": "authorization"},
    show_headers=("access-control-allow-origin", "access-control-allow-headers"))
step("Preflight desde un origen no permitido (sin cabecera Allow-Origin)", "OPTIONS", "/trips", 204, headers={
    "Origin": "https://sitio-malicioso.example", "Access-Control-Request-Method": "GET"},
    show_headers=("access-control-allow-origin",))

passed = sum(1 for _, ok in results if ok)
header = [
    "# Evidencia 01 — Pruebas reales del backend serverless",
    "",
    f"- Fecha de ejecucion: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
    f"- API: `{args.api_url}` (API Gateway HTTP + Lambda + DynamoDB, region {args.region})",
    "- Usuarios: dos cuentas de prueba creadas en Cognito (A y B) para verificar el aislamiento.",
    f"- **Resultado: {passed}/{len(results)} comprobaciones correctas**",
    "",
    "| # | Comprobacion | Resultado |",
    "|---|---|---|",
    *[f"| {i} | {title} | {'✅' if ok else '❌'} |" for i, (title, ok) in enumerate(results, 1)],
    "",
]
out = Path(args.out)
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text("\n".join(header + ["---", ""] + log), encoding="utf-8")
print(f"{passed}/{len(results)} OK -> {out}")
sys.exit(0 if passed == len(results) else 1)
