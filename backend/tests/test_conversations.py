"""Historial de conversaciones desde la memoria del agente (AgentCore Memory simulada)."""

import json
from datetime import datetime, timedelta, timezone

import pytest

import conversations
from conftest import USER_A, USER_B, call

T0 = datetime(2026, 11, 16, 10, 0, 0, tzinfo=timezone.utc)


def conv(role, blocks, minutes, event_id):
    body = {"message": {"role": role, "content": blocks}, "message_id": 0}
    return {"eventId": event_id, "eventTimestamp": T0 + timedelta(minutes=minutes),
            "payload": [{"conversational": {"role": role.upper(), "content": {"text": json.dumps(body)}}}]}


def ui_event(prompt, ui, minutes, event_id):
    return {"eventId": event_id, "eventTimestamp": T0 + timedelta(minutes=minutes),
            "payload": [{"blob": json.dumps({"prompt": prompt, "ui": ui})}]}


class FakeMemory:
    """list_sessions / list_events / delete_event sobre un diccionario {(actor, session): [eventos]}."""

    def __init__(self, store):
        self.store = store
        self.deleted = []

    def list_sessions(self, memoryId, actorId, maxResults=100, nextToken=None):
        sessions = sorted({s for (a, s) in self.store if a == actorId})
        return {"sessionSummaries": [{"sessionId": s, "actorId": actorId, "createdAt": T0} for s in sessions]}

    def list_events(self, memoryId, actorId, sessionId, includePayloads=True, maxResults=100, nextToken=None):
        return {"events": list(self.store.get((actorId, sessionId), []))}

    def delete_event(self, memoryId, actorId, sessionId, eventId):
        self.store[(actorId, sessionId)] = [e for e in self.store[(actorId, sessionId)] if e["eventId"] != eventId]
        self.deleted.append(eventId)


SESSION = "11111111-2222-3333-4444-555555555555"


@pytest.fixture
def memory(monkeypatch):
    store = {
        (USER_A, SESSION): [
            conv("user", [{"text": "Dame el clima en Cartagena"}], 1, "a1"),
            conv("assistant", [{"toolUse": {"name": "ask_weather", "input": {}}}], 2, "a2"),
            conv("user", [{"toolResult": {"toolUseId": "x", "content": [{"text": "datos"}]}}], 3, "a3"),
            conv("assistant", [{"text": "Hará calor, 31 °C."}], 4, "a4"),
            conv("user", [{"text": "Gracias"}], 6, "a5"),
            conv("assistant", [{"text": "¡De nada!"}], 7, "a6"),
        ],
        (f"ui-{USER_A}", SESSION): [
            ui_event("Dame el clima en Cartagena", [{"component": "weather", "data": {"city": "Cartagena"}}], 5, "u1"),
            ui_event("Gracias", [], 8, "u2"),
        ],
        (USER_B, "99999999-aaaa-bbbb-cccc-000000000000"): [conv("user", [{"text": "secreto de B"}], 1, "b1")],
        (f"ui-{USER_B}", "99999999-aaaa-bbbb-cccc-000000000000"): [ui_event("secreto de B", [], 2, "bu1")],
    }
    fake = FakeMemory(store)
    monkeypatch.setattr(conversations, "MEMORY_ID", "mem-test")
    monkeypatch.setattr(conversations, "_client", fake)
    return fake


def test_lista_las_conversaciones_del_usuario_con_titulo(memory):
    status, data = call("conversations", "GET /conversations")
    assert status == 200
    assert [c["id"] for c in data["conversations"]] == [SESSION]
    assert data["conversations"][0]["title"] == "Dame el clima en Cartagena" and data["conversations"][0]["turns"] == 2


def test_reconstruye_mensajes_con_herramientas_tarjetas_y_texto(memory):
    status, data = call("conversations", "GET /conversations/{id}", path={"id": SESSION})
    assert status == 200
    m = data["messages"]
    assert [x["role"] for x in m] == ["user", "assistant", "user", "assistant"]
    assert m[0]["text"] == "Dame el clima en Cartagena"
    kinds = [b["type"] for b in m[1]["blocks"]]
    assert kinds == ["tool", "ui", "text"]
    assert m[1]["blocks"][1]["component"] == "weather" and m[1]["blocks"][2]["text"] == "Hará calor, 31 °C."
    assert m[3]["blocks"] == [{"type": "text", "text": "¡De nada!"}]  # el resultado de la herramienta no se muestra como mensaje


def test_un_usuario_no_ve_las_conversaciones_de_otro(memory):
    assert call("conversations", "GET /conversations", sub=USER_B)[1]["conversations"][0]["title"] == "secreto de B"
    assert call("conversations", "GET /conversations/{id}", sub=USER_B, path={"id": SESSION})[0] == 404
    assert call("conversations", "DELETE /conversations/{id}", sub=USER_B, path={"id": SESSION})[0] == 404
    assert call("conversations", "GET /conversations", sub=None)[0] == 401


def test_id_de_sesion_invalido(memory):
    assert call("conversations", "GET /conversations/{id}", path={"id": "../../x"})[0] == 404
    assert call("conversations", "GET /conversations/{id}", path={"id": "12"})[0] == 404


def test_eliminar_borra_los_eventos_del_agente_y_de_las_tarjetas(memory):
    status, data = call("conversations", "DELETE /conversations/{id}", path={"id": SESSION})
    assert status == 200 and data["events"] == 8
    assert sorted(memory.deleted) == ["a1", "a2", "a3", "a4", "a5", "a6", "u1", "u2"]
    assert call("conversations", "GET /conversations/{id}", path={"id": SESSION})[0] == 404
    # lo de B sigue intacto
    assert len(call("conversations", "GET /conversations", sub=USER_B)[1]["conversations"]) == 1


def test_sin_memoria_configurada_responde_503(monkeypatch):
    monkeypatch.setattr(conversations, "MEMORY_ID", "")
    assert call("conversations", "GET /conversations")[0] == 503


def test_usuario_sin_conversaciones_devuelve_lista_vacia(memory, monkeypatch):
    from botocore.exceptions import ClientError

    def missing(**kwargs):
        raise ClientError({"Error": {"Code": "ResourceNotFoundException", "Message": "Actor not found"}}, "ListSessions")

    monkeypatch.setattr(memory, "list_sessions", missing)
    status, data = call("conversations", "GET /conversations")
    assert status == 200 and data["conversations"] == []
