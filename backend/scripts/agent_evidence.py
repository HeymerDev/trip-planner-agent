"""
Conversacion real, de varios turnos, contra el Orchestrator DESPLEGADO usando HTTP streaming y el JWT de
Cognito (el mismo camino que el navegador). Registra herramientas usadas, componentes de UI y texto
(T-36, T-70). Genera docs/evidencias/02-agentes-streaming.md.

Uso (desde backend/): .venv/Scripts/python.exe scripts/agent_evidence.py --api-url ... --agent-url ... --client-id ... --email ... --password ...
"""

import argparse
import json
import sys
import time
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

import boto3

p = argparse.ArgumentParser()
p.add_argument("--agent-url", required=True)
p.add_argument("--api-url", required=True)
p.add_argument("--client-id", required=True)
p.add_argument("--email", required=True)
p.add_argument("--password", required=True)
p.add_argument("--region", default="us-east-2")
p.add_argument("--out", default=str(Path(__file__).resolve().parents[2] / "docs" / "evidencias" / "02-agentes-streaming.md"))
args = p.parse_args()

token = boto3.client("cognito-idp", region_name=args.region).initiate_auth(
    ClientId=args.client_id, AuthFlow="USER_PASSWORD_AUTH",
    AuthParameters={"USERNAME": args.email, "PASSWORD": args.password},
)["AuthenticationResult"]["AccessToken"]

session = str(uuid.uuid4())  # misma sesion en todos los turnos: el agente conserva el contexto

TURNS = [
    ("Paso 2-6 · Consulta del escenario (clima, vuelos, hoteles) — NO debe crear nada todavía",
     "Quiero organizar unas vacaciones de cuatro días en Cartagena, del 20 al 23 de noviembre de 2026. Salgo desde Bogotá, "
     "viajo con dos personas más y tengo un presupuesto de 5 millones de pesos. Quiero conocer el clima, encontrar vuelos "
     "y organizar algunas actividades turísticas."),
    ("Paso 7 · El usuario pide crear el viaje", "Perfecto, crea el viaje con esos datos."),
    ("Paso 8 · Se genera y guarda el itinerario",
     "Genera un itinerario de 4 días con actividades turísticas que quepan en el presupuesto, adaptado al clima, y guárdalo."),
    ("Paso 9a · Recarga del monedero simulado", "Recarga 3.000.000 COP en mi monedero."),
    ("Paso 9b · Solicita reservar (el agente debe pedir confirmación antes de cobrar)",
     "Quiero reservar una noche en el hotel que más te guste de los que encontraste."),
    ("Paso 9c · Confirmación explícita → compra simulada", "Sí, confirmo la compra con el saldo del monedero."),
    ("Paso 12 · Recuperación de datos", "Muéstrame mis viajes, mis reservas y mi saldo."),
]

results = []
for title, prompt in TURNS:
    started = time.time()
    request = urllib.request.Request(
        args.agent_url, method="POST", data=json.dumps({"prompt": prompt}).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json", "Accept": "text/event-stream",
                 "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": session},
    )
    tools, ui, text, first_byte, errors = [], [], [], None, []
    try:
        with urllib.request.urlopen(request, timeout=290) as response:
            status = response.status
            for raw in response:
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("data:"):
                    continue
                if first_byte is None:
                    first_byte = time.time() - started
                try:
                    ev = json.loads(line[5:].strip())
                except json.JSONDecodeError:
                    continue
                if isinstance(ev, str):
                    try:
                        ev = json.loads(ev)
                    except json.JSONDecodeError:
                        continue
                inner = ev.get("event", {}) if isinstance(ev, dict) else {}
                tool = inner.get("contentBlockStart", {}).get("start", {}).get("toolUse", {}).get("name")
                if tool:
                    tools.append(tool)
                delta = inner.get("contentBlockDelta", {}).get("delta", {}).get("text")
                if delta:
                    text.append(delta)
                if isinstance(ev, dict) and "ui" in ev:
                    ui.append(ev["ui"]["component"])
                if isinstance(ev, dict) and "error" in ev:
                    errors.append(str(ev["error"]))
    except Exception as exc:  # noqa: BLE001
        status = f"ERROR {exc}"
    results.append({"title": title, "prompt": prompt, "status": status, "tools": tools, "ui": ui,
                    "text": "".join(text), "errors": errors, "secs": time.time() - started, "ttfb": first_byte})
    print(f"{title}: {status} tools={tools} ui={ui} ({results[-1]['secs']:.0f}s)")

lines = [
    "# Evidencia 02 — Agentes por HTTP streaming (escenario de demostración)",
    "",
    f"- Fecha: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
    f"- Canal: navegador → AgentCore Runtime **directo** (HTTP streaming, SSE) con JWT de Cognito; sesión `{session}`",
    "- El Orchestrator delega en Flights / Weather / Hotels por A2A (SigV4) y usa las Tools de negocio (Lambda → DynamoDB).",
    "",
    "| Turno | HTTP | Tools invocadas | Componentes de UI emitidos | 1.er byte | Total |",
    "|---|---|---|---|---|---|",
]
for r in results:
    lines.append(f"| {r['title'].split(' · ')[0]} | {r['status']} | {', '.join(r['tools']) or '—'} | {', '.join(r['ui']) or '—'} | "
                 f"{(r['ttfb'] or 0):.1f}s | {r['secs']:.0f}s |")
lines += ["", "---", ""]
for r in results:
    lines += [f"## {r['title']}", "", f"**Usuario:** {r['prompt']}", "",
              f"**Herramientas:** {' → '.join(r['tools']) or '—'}  ", f"**Componentes de UI:** {', '.join(r['ui']) or '—'}", ""]
    if r["errors"]:
        lines += [f"**Errores:** {r['errors']}", ""]
    lines += ["**Respuesta del asistente (texto en streaming):**", "", *["> " + l for l in (r["text"] or "(sin texto)").splitlines()], ""]
out = Path(args.out)
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text("\n".join(lines), encoding="utf-8")
print("->", out)
sys.exit(0)
