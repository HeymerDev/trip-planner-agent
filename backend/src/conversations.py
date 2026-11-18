"""
Lambda `conversations`: historial de conversaciones guardado en la MEMORIA del agente (AgentCore Memory).

El Orchestrator ya guarda cada mensaje de la sesion en la memoria (actor = `sub` del usuario). Ademas guarda,
al final de cada turno, las tarjetas que mostro (vuelos, clima, hoteles, viajes...) en un actor hermano
`ui-<sub>` de la MISMA memoria, para poder reconstruir la conversacion completa. Esta Lambda las lee y las
une; el actor sale SIEMPRE del JWT, asi que un usuario solo puede leer/borrar sus propias conversaciones.

Nota: la memoria conversacional ayuda al agente; DynamoDB sigue siendo la fuente de verdad de viajes y reservas.
"""

import json
import os
import re
from concurrent.futures import ThreadPoolExecutor

import boto3
from botocore.exceptions import ClientError

from common import ApiError, make_handler, not_found, response

MEMORY_ID = os.environ.get("MEMORY_ID", "")
SESSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{8,99}$")
MAX_SESSIONS = 30
MAX_EVENTS = 1000

_client = None


def client():
    global _client
    if _client is None:
        _client = boto3.client("bedrock-agentcore")
    return _client


def ui_actor(sub: str) -> str:
    return f"ui-{sub}"


# ---------------------------------------------------------------------------- lectura de la memoria


def _not_found(error: ClientError) -> bool:
    return error.response.get("Error", {}).get("Code") == "ResourceNotFoundException"


def _events(actor: str, session: str) -> list[dict]:
    items, token = [], None
    while True:
        kwargs = {"memoryId": MEMORY_ID, "actorId": actor, "sessionId": session, "includePayloads": True, "maxResults": 100}
        if token:
            kwargs["nextToken"] = token
        try:
            result = client().list_events(**kwargs)
        except ClientError as error:
            if _not_found(error):  # actor o sesion aun sin eventos
                return []
            raise
        items += result.get("events", [])
        token = result.get("nextToken")
        if not token or len(items) >= MAX_EVENTS:
            break
    items.sort(key=lambda e: e["eventTimestamp"])
    return items


def _sessions(actor: str) -> list[dict]:
    items, token = [], None
    while True:
        kwargs = {"memoryId": MEMORY_ID, "actorId": actor, "maxResults": 100}
        if token:
            kwargs["nextToken"] = token
        try:
            result = client().list_sessions(**kwargs)
        except ClientError as error:
            if _not_found(error):  # el usuario aun no tiene conversaciones guardadas
                return []
            raise
        items += result.get("sessionSummaries", [])
        token = result.get("nextToken")
        if not token or len(items) >= 500:
            break
    return items


def _message(event: dict):
    """(rol, bloques) de un evento conversacional del Strands session manager, o None."""
    for part in event.get("payload", []):
        conversational = part.get("conversational")
        if not conversational:
            continue
        try:
            data = json.loads(conversational["content"]["text"])
        except (KeyError, TypeError, ValueError):
            continue
        message = data.get("message") or {}
        if message.get("role") in ("user", "assistant"):
            return message["role"], message.get("content") or []
    return None


def _ui_payload(event: dict) -> dict | None:
    for part in event.get("payload", []):
        blob = part.get("blob")
        if blob is None:
            continue
        try:
            data = json.loads(blob) if isinstance(blob, str) else blob
        except ValueError:
            continue
        if isinstance(data, dict) and "ui" in data:
            return data
    return None


def build_messages(agent_events: list[dict], ui_events: list[dict]) -> list[dict]:
    """
    Une los mensajes del agente (texto y herramientas) con las tarjetas guardadas por turno.
    Un turno = mensaje del usuario + respuesta del asistente: [indicadores de herramienta, tarjetas, texto].
    """
    turns: list[dict] = []
    for event in sorted(agent_events, key=lambda e: e["eventTimestamp"]):
        parsed = _message(event)
        if not parsed:
            continue
        role, blocks = parsed
        if role == "user":
            texts = [b["text"] for b in blocks if isinstance(b, dict) and "text" in b]
            has_tool_result = any(isinstance(b, dict) and "toolResult" in b for b in blocks)
            if texts and not has_tool_result:
                turns.append({"start": event["eventTimestamp"], "user": "\n".join(texts), "tools": [], "ui": [], "texts": []})
        elif turns:
            for block in blocks:
                if not isinstance(block, dict):
                    continue
                if block.get("text"):
                    turns[-1]["texts"].append(block["text"])
                elif "toolUse" in block:
                    turns[-1]["tools"].append(block["toolUse"].get("name", ""))

    for event in sorted(ui_events, key=lambda e: e["eventTimestamp"]):
        payload = _ui_payload(event)
        if not payload:
            continue
        owner = [t for t in turns if t["start"] <= event["eventTimestamp"]]
        if owner:
            owner[-1]["ui"].extend(payload.get("ui") or [])

    messages: list[dict] = []
    for turn in turns:
        blocks = [{"type": "tool", "name": name} for name in turn["tools"] if name]
        blocks += [{"type": "ui", "component": u["component"], "data": u["data"]} for u in turn["ui"] if "component" in u]
        blocks += [{"type": "text", "text": text} for text in turn["texts"]]
        messages.append({"role": "user", "text": turn["user"]})
        messages.append({"role": "assistant", "blocks": blocks})
    return messages


# ------------------------------------------------------------------------------------- endpoints


def _require_memory():
    if not MEMORY_ID:
        raise ApiError(503, "MEMORY_NOT_CONFIGURED", "El historial de conversaciones no esta configurado.")


def _summary(sub: str, session: dict) -> dict | None:
    events = _events(ui_actor(sub), session["sessionId"])
    payloads = [(e, _ui_payload(e)) for e in events]
    payloads = [(e, p) for e, p in payloads if p]
    if not payloads:
        return None
    first, last = payloads[0][1], payloads[-1]
    title = (first.get("prompt") or "Conversacion").strip().replace("\n", " ")
    return {
        "id": session["sessionId"],
        "title": title[:70],
        "updatedAt": last[0]["eventTimestamp"].isoformat() if hasattr(last[0]["eventTimestamp"], "isoformat") else str(last[0]["eventTimestamp"]),
        "turns": len(payloads),
    }


def list_conversations(event, sub):
    _require_memory()
    sessions = sorted(_sessions(ui_actor(sub)), key=lambda s: s["createdAt"], reverse=True)[:MAX_SESSIONS]
    with ThreadPoolExecutor(max_workers=8) as pool:
        summaries = [s for s in pool.map(lambda s: _summary(sub, s), sessions) if s]
    summaries.sort(key=lambda s: s["updatedAt"], reverse=True)
    return response(200, {"conversations": summaries})


def _session_id(event) -> str:
    session = (event.get("pathParameters") or {}).get("id", "")
    if not SESSION_RE.match(session):
        raise not_found("Conversacion")
    return session


def get_conversation(event, sub):
    _require_memory()
    session = _session_id(event)
    ui_events = _events(ui_actor(sub), session)
    agent_events = _events(sub, session)
    if not ui_events and not agent_events:
        raise not_found("Conversacion")
    messages = build_messages(agent_events, ui_events)
    first_user = next((m["text"] for m in messages if m["role"] == "user"), "Conversacion")
    return response(200, {"id": session, "title": first_user[:70], "messages": messages})


def delete_conversation(event, sub):
    _require_memory()
    session = _session_id(event)
    targets = [(actor, e["eventId"]) for actor in (sub, ui_actor(sub)) for e in _events(actor, session)]
    if not targets:
        raise not_found("Conversacion")

    def remove(target):
        client().delete_event(memoryId=MEMORY_ID, actorId=target[0], sessionId=session, eventId=target[1])

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(remove, targets))
    return response(200, {"deleted": True, "id": session, "events": len(targets)})


handler = make_handler(
    {
        "GET /conversations": list_conversations,
        "GET /conversations/{id}": get_conversation,
        "DELETE /conversations/{id}": delete_conversation,
    }
)
