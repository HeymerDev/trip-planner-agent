"""
OrchestratorAgent - Punto de entrada del usuario. Consulta a FlightsAgent,
WeatherAgent y HotelsAgent mediante el protocolo A2A y consolida sus
respuestas en un plan de viaje. No importa codigo de los agentes
especialistas: los invoca solo a traves de sus endpoints A2A remotos
(FLIGHTS_AGENT_URL / WEATHER_AGENT_URL / HOTELS_AGENT_URL).
"""

import asyncio
import json
import os
from collections import OrderedDict
from datetime import date, datetime, timezone
from typing import Any

import boto3
import httpx
from a2a.client import ClientConfig
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from strands import Agent, ModelRetryStrategy, tool
from strands.agent.a2a_agent import A2AAgent
from strands.agent.conversation_manager.null_conversation_manager import NullConversationManager
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from bedrock_agentcore.memory.integrations.strands.config import AgentCoreMemoryConfig
from bedrock_agentcore.memory.integrations.strands.session_manager import AgentCoreMemorySessionManager
import ui
from business_tools import BUSINESS_TOOLS
from mcp_client.client import get_gateway_mcp_client
from model.load import load_model

# strands.telemetry.tracer unconditionally calls ThreadingInstrumentor().instrument(),
# which has a known upstream bug: it attaches an OTEL context token on one thread/task
# and can detach it from a different one (contextvars "Token was created in a different
# Context" ValueError), crashing mid-conversation. Tracing doesn't need cross-thread
# context propagation here, so disable it before strands gets a chance to apply it.
from opentelemetry.instrumentation.threading import ThreadingInstrumentor

ThreadingInstrumentor.instrument = lambda self, **kwargs: None

app = BedrockAgentCoreApp()
log = app.logger

FLIGHTS_AGENT_URL = os.environ["FLIGHTS_AGENT_URL"]
WEATHER_AGENT_URL = os.environ["WEATHER_AGENT_URL"]
HOTELS_AGENT_URL = os.environ["HOTELS_AGENT_URL"]
# Local override first; when deployed, the CLI injects MEMORY_<NAME>_ID for the memory it created.
MEMORY_ID = os.environ.get("MEMORY_ID") or os.environ.get("MEMORY_TRIPPLANNERMEMORY_ID", "")

# "sigv4": sign every A2A call with this runtime's AWS credentials, which is what a deployed
# specialist runtime (authorizerType AWS_IAM) requires. "none": plain calls, for the local
# specialists started by dev-all.ps1, which don't enforce any auth.
A2A_AUTH_MODE = os.environ.get("A2A_AUTH_MODE", "none").lower()
A2A_SIGV4_SERVICE = "bedrock-agentcore"


class SigV4HttpxAuth(httpx.Auth):
    """Signs outgoing httpx requests with the caller's AWS credentials (SigV4)."""

    requires_request_body = True

    def __init__(self, service: str = A2A_SIGV4_SERVICE, region: str | None = None):
        self._session = boto3.Session()
        self._service = service
        self._region = region or self._session.region_name

    def auth_flow(self, request: httpx.Request):
        credentials = self._session.get_credentials()
        if credentials is None:
            raise RuntimeError("No AWS credentials available to SigV4-sign the A2A request")

        headers = {}
        if "content-type" in request.headers:
            headers["Content-Type"] = request.headers["content-type"]
        signed = AWSRequest(method=request.method, url=str(request.url), data=request.content, headers=headers)
        SigV4Auth(credentials.get_frozen_credentials(), self._service, self._region).add_auth(signed)

        for name in ("Authorization", "X-Amz-Date", "X-Amz-Security-Token"):
            if name in signed.headers:
                request.headers[name] = signed.headers[name]
        yield request


async def _ask_remote(endpoint: str, request: str) -> str:
    """Send a natural-language request to a remote A2A specialist and return its text answer."""
    if A2A_AUTH_MODE == "sigv4":
        async def _log_error(response: httpx.Response) -> None:
            if response.status_code >= 400:
                await response.aread()
                log.error("A2A %s %s -> %s %s", response.request.method, response.request.url,
                             response.status_code, response.text[:500])

        auth = SigV4HttpxAuth()
        log.info("A2A SigV4 region=%s", auth._region)
        async with httpx.AsyncClient(auth=auth, timeout=300, event_hooks={"response": [_log_error]}) as client:
            remote = A2AAgent(endpoint=endpoint, client_config=ClientConfig(httpx_client=client))
            result = await remote.invoke_async(request)
    else:
        remote = A2AAgent(endpoint=endpoint)
        result = await remote.invoke_async(request)
    answer = _message_text(result.message)
    log.info("A2A request=%r -> response=%r", request[:300], answer[:400])
    return _specialist_answer(answer)


def _specialist_answer(text: str) -> str:
    """
    Los especialistas terminan su respuesta con un bloque <ui>{json}</ui> con datos estructurados
    (vuelos, clima, hoteles). Se publican como componentes para la interfaz y el modelo solo recibe
    el texto, de modo que no copie ni altere el JSON.
    """
    ui.remember_links(text)
    clean, events = ui.extract_ui(text)
    for event in events:
        ui.emit(event["component"], event["data"])
    if events:
        clean += "\n\n(Los datos estructurados ya se muestran al usuario como tarjetas; no los repitas en JSON.)"
    return clean


def _message_text(message) -> str:
    """Plain text of an A2A answer. str(message) would hand the model a dict repr, with the
    newlines escaped and the links buried inside it."""
    if isinstance(message, dict):
        texts = [block["text"] for block in message.get("content", []) if isinstance(block, dict) and "text" in block]
        if texts:
            return "\n".join(texts)
    return str(message)


@tool
async def ask_flights(request: str) -> str:
    """
    Consulta al agente remoto de vuelos (FlightsAgent) via el protocolo A2A.

    Usa esta herramienta cuando necesites informacion sobre vuelos, horarios,
    aerolineas o precios entre ciudades colombianas. Reenvia la solicitud del
    usuario en lenguaje natural, incluyendo origen, destino y fecha si estan
    disponibles.

    Args:
        request: Pregunta o solicitud en lenguaje natural para el agente de vuelos.

    Returns:
        La respuesta en texto generada por el agente remoto de vuelos.
    """
    return await _ask_remote(FLIGHTS_AGENT_URL, request)


@tool
async def ask_weather(request: str) -> str:
    """
    Consulta al agente remoto de clima (WeatherAgent) via el protocolo A2A.

    Usa esta herramienta cuando necesites informacion sobre el clima, la
    temperatura, la humedad o las condiciones atmosfericas esperadas en una
    ciudad. Reenvia la solicitud del usuario en lenguaje natural, incluyendo
    la ciudad y la fecha si estan disponibles.

    Args:
        request: Pregunta o solicitud en lenguaje natural para el agente de clima.

    Returns:
        La respuesta en texto generada por el agente remoto de clima.
    """
    return await _ask_remote(WEATHER_AGENT_URL, request)


@tool
async def ask_hotels(request: str) -> str:
    """
    Consulta al agente remoto de hospedaje (HotelsAgent) via el protocolo A2A.

    Usa esta herramienta cuando necesites informacion sobre hoteles,
    alojamiento, zonas o precios por noche en una ciudad colombiana. Reenvia
    la solicitud del usuario en lenguaje natural, incluyendo la ciudad y las
    fechas de entrada y salida si estan disponibles.

    Args:
        request: Pregunta o solicitud en lenguaje natural para el agente de hospedaje.

    Returns:
        La respuesta en texto generada por el agente remoto de hospedaje.
    """
    return await _ask_remote(HOTELS_AGENT_URL, request)


tools = [ask_flights, ask_weather, ask_hotels, *BUSINESS_TOOLS]

DEFAULT_SYSTEM_PROMPT = """
Eres TripPlanner AI, un asistente que ayuda a planificar y GESTIONAR viajes desde Colombia.
Hoy es {today}. Coordinas especialistas y operas los datos del usuario con herramientas.

ESPECIALISTAS (A2A)
- ask_flights: vuelos reales (precios, horarios, enlaces de compra).
- ask_weather: pronostico del clima (hasta 16 dias hacia adelante).
- ask_hotels: hoteles reales con enlace de reserva.
Reenvia a cada uno la peticion con ciudades, fechas y numero de viajeros. No inventes vuelos, precios,
hoteles ni clima: si un especialista falla o no tiene datos, dilo.
Los datos que estos agentes devuelven ya se muestran al usuario como tarjetas visuales; tu respuesta debe
ser un resumen breve y util (la mejor opcion y por que), no una lista completa repetida.

HERRAMIENTAS DE NEGOCIO (guardan en la base de datos del usuario)
- Viajes: create_trip, get_trips, update_trip. Itinerario: create_itinerary, update_itinerary.
- Reservas: create_reservation, get_reservations, update_reservation.
- Monedero simulado: get_wallet, top_up_wallet. Divisas: convert_currency. Transporte: compare_transport.
Reglas:
0. Haz solo lo que el usuario pidio. Si describe un viaje y pide informacion (vuelos, clima, hoteles,
   actividades), consulta a los especialistas y PROPON un plan, pero NO crees el viaje, el itinerario ni
   reservas hasta que el usuario lo pida o lo confirme. Si faltan fechas, pregunta por ellas (y por cualquier
   otro dato imprescindible) en un solo mensaje breve antes de consultar. El clima solo existe hasta 16 dias
   desde hoy: si las fechas estan mas lejos, dilo y no lo consultes.
0b. NUNCA llames create_trip, create_itinerary, create_reservation, update_trip, update_itinerary,
   update_reservation ni top_up_wallet salvo que el usuario haya pedido o aceptado de forma explicita esa
   accion (por ejemplo "crea el viaje", "guardalo", "reserva", "recarga", "si"). Describir un plan o pedir
   informacion NO es pedir que lo guardes.
0c. Honestidad: solo afirma que creaste, guardaste, reservaste o actualizaste algo si en ESTE turno llamaste a la
   herramienta y respondio con exito. Si no la llamaste, di que aun no lo has hecho y ofrece hacerlo.
0d. Si un especialista informa un error, falta de cuota o ausencia de datos, repite el motivo real al usuario
   (por ejemplo "se agoto la cuota del servicio de vuelos"); no lo disfraces de "intermitencias" ni inventes datos.
   Pide el clima de a lo sumo 4 dias por consulta (una sola llamada a ask_weather).
1. Antes de crear un viaje confirma que tienes origen, destino, fechas, viajeros y presupuesto; si falta algo, preguntalo.
2. Para modificar o reservar necesitas el id del viaje: si no lo tienes, llama get_trips. Nunca inventes ids.
3. Itinerario: propone actividades concretas dia por dia con hora, lugar y costo estimado en COP (el costo total
   debe caber en el presupuesto). Adapta las actividades al clima consultado (lluvia = planes bajo techo) y a las
   preferencias del usuario. Guardalo con create_itinerary (o update_itinerary si ya existe).
4. COMPRAS: nunca cobres sin confirmacion explicita. Antes de create_reservation con pay=true muestra que vas a
   comprar y cuanto cuesta, y espera el "si". Si el precio viene en USD u otra moneda, convierte con
   convert_currency y usa el valor en COP (guarda tambien original_price, original_currency y fx_rate). Usa una
   idempotency_key unica y estable por compra. Si el saldo es insuficiente, informa el saldo y ofrece recargar con
   top_up_wallet, que solo puedes ejecutar si el usuario acepta un monto. Nunca pidas ni aceptes datos de tarjeta.
5. Todas las reservas son SIMULADAS: no hay cobro real, y debes decirlo cuando compres.
6. Para trayectos cortos compara con compare_transport y recomienda bus o avion; aclara que el bus es una estimacion.
7. Presupuesto: al sugerir vuelo + hotel + actividades, suma los costos y avisa si superan el presupuesto.
8. Montos de dinero en COP con separador de miles (por ejemplo 1.250.000 COP).
9. Herramientas extra del gateway (consejos de ciudad) pueden estar disponibles; usalas si ayudan.

Enlaces: cuando un especialista entregue URLs (compra de vuelo, reserva de hotel), incluyelas siempre junto a la
opcion que corresponde, en formato [texto](url), copiadas exactamente; no las modifiques ni inventes ninguna.
Responde siempre en espanol, de forma clara y organizada.
"""


def _persist_turn_ui(actor_id: str, session_id: str, prompt: str, ui_events: list[dict]) -> None:
    """
    Guarda en la MEMORIA de AgentCore las tarjetas (vuelos, clima, hoteles, viajes...) que se mostraron en este turno,
    en el actor hermano `ui-<sub>` de la misma memoria. Los mensajes de la conversacion ya los guarda el session
    manager de Strands; con ambos, la Lambda `conversations` reconstruye la conversacion completa para la interfaz.
    """
    if not MEMORY_ID or MEMORY_ID == "PENDING_MEMORY_ID" or not actor_id or actor_id == "default-user":
        return
    try:
        boto3.client("bedrock-agentcore").create_event(
            memoryId=MEMORY_ID,
            actorId=f"ui-{actor_id}",
            sessionId=session_id,
            eventTimestamp=datetime.now(timezone.utc),
            payload=[{"blob": json.dumps({"prompt": prompt, "ui": ui_events}, ensure_ascii=False, default=str)}],
        )
    except Exception:  # noqa: BLE001 - el historial de tarjetas es accesorio: nunca debe romper el chat
        log.exception("No se pudieron guardar las tarjetas del turno en la memoria")


def _make_conversation_manager():
    return NullConversationManager()


def _make_session_manager(session_id: str, actor_id: str) -> AgentCoreMemorySessionManager | None:
    """Wire this session to AgentCore Memory so history survives cold starts.

    actor_id identifies the end user (from the invocation context), not the
    agent — the memory's USER_PREFERENCE/SEMANTIC strategies namespace
    recollections by {actorId}, so a fixed per-agent value here would mix
    every caller's preferences into one shared bucket.

    Returns None when MEMORY_ID is unset (local dev without a deployed Memory
    resource) so the agent still runs, just without durable history.
    """
    if not MEMORY_ID or MEMORY_ID == "PENDING_MEMORY_ID":
        return None
    return AgentCoreMemorySessionManager(
        agentcore_memory_config=AgentCoreMemoryConfig(
            memory_id=MEMORY_ID,
            session_id=session_id,
            actor_id=actor_id,
        ),
    )


# Reuses one Agent per session_id so each session keeps its own in-process
# conversation history as a fast warm-instance cache. The cache is bounded to
# 128 sessions with LRU eviction (least-recently-used is dropped and its
# history reset) so a single process serving many sessions cannot leak history
# between them or grow without limit. Durable, cross-cold-start history comes
# from the AgentCoreMemorySessionManager attached to each agent.
def agent_factory():
    cache = OrderedDict()

    def get_or_create_agent(session_id, actor_id):
        if session_id in cache:
            cache.move_to_end(session_id)
            return cache[session_id]
        if len(cache) >= 128:
            cache.popitem(last=False)
        # One token per session: Cognito M2M tokens last 1h, and the agent is cached per session.
        gateway_client = get_gateway_mcp_client()
        cache[session_id] = Agent(
            model=load_model(),
            system_prompt=DEFAULT_SYSTEM_PROMPT.format(today=date.today().isoformat()),
            tools=[*tools, gateway_client] if gateway_client else tools,
            conversation_manager=_make_conversation_manager(),
            session_manager=_make_session_manager(session_id, actor_id),
            # Gemini's lite/preview models return transient 503s under load more often
            # than the default retry budget (6 attempts, ~2min) tolerates. Give it more
            # room before giving up.
            retry_strategy=ModelRetryStrategy(max_attempts=10, initial_delay=5, max_delay=60),
            # This agent is served over HTTP, not an interactive console, so the default
            # PrintingCallbackHandler's per-token print() is both useless and a crash
            # risk: it raises UnicodeEncodeError on Windows' cp1252 console for any
            # response containing characters outside that codepage, which then corrupts
            # OTEL's span-context stack during the generator's teardown.
            callback_handler=None,
        )
        return cache[session_id]

    return get_or_create_agent


get_or_create_agent = agent_factory()


def strip_trailing_tool_use(messages: Any) -> list[dict]:
    """Strip toolUse blocks from the tail until the last message has none."""
    if not isinstance(messages, list):
        raise ValueError("messages must be a list")

    messages = list(messages)
    while messages:
        last = messages[-1]
        if not isinstance(last, dict):
            raise ValueError("each message must be an object")
        original_content = last.get("content", [])
        if not isinstance(original_content, list) or not all(isinstance(block, dict) for block in original_content):
            raise ValueError("each message content value must be a list of content blocks")

        content = [block for block in original_content if "toolUse" not in block]
        if len(content) == len(original_content):
            break
        if content:
            messages[-1] = {**last, "content": content}
            break
        messages.pop()

    return messages


def _extract_prompt(payload: dict):
    """Accept validated harness messages, tool results, or a plain prompt string."""
    if not isinstance(payload, dict):
        raise ValueError("payload must be a JSON object")
    if "messages" in payload:
        return strip_trailing_tool_use(payload["messages"])
    if "tool_results" in payload:
        tool_results = payload["tool_results"]
        if not isinstance(tool_results, list) or not all(
            isinstance(tool_result, dict) and isinstance(tool_result.get("toolUseId"), str)
            for tool_result in tool_results
        ):
            raise ValueError("tool_results must contain objects with a toolUseId string")
        return [{"role": "user", "content": [{"toolResult": {
            "toolUseId": tr["toolUseId"],
            "status": tr.get("status", "success"),
            "content": tr.get("content", []),
        }} for tr in tool_results]}]
    prompt = payload.get("prompt", "")
    if not isinstance(prompt, str):
        raise ValueError("prompt must be a string")
    return prompt


@app.entrypoint
async def invoke(payload, context):
    log.info("Invoking OrchestratorAgent.....")

    session_id = getattr(context, "session_id", "default-session")
    headers = getattr(context, "request_headers", None) or {}
    # La identidad sale del JWT de Cognito (AgentCore ya valido su firma). Es el actor de la memoria
    # y el token que las Tools de negocio reenvian a la API.
    prompt = _extract_prompt(payload)
    user_text = prompt if isinstance(prompt, str) else ""
    state = ui.begin(next((v for k, v in headers.items() if k.lower() == "authorization"), None), session_id, user_text)
    actor_id = state.user_id or getattr(context, "actor_id", None) or "default-user"
    agent = get_or_create_agent(session_id, actor_id)

    shown: list[dict] = []  # tarjetas de este turno, para guardarlas en la memoria
    async for event in agent.stream_async(prompt):
        # Datos estructurados que publicaron las Tools desde el ultimo evento (Agent-Driven UI).
        for ui_event in ui.drain():
            shown.append(ui_event)
            yield {"ui": ui_event}
        if not isinstance(event, dict) or "event" not in event:
            continue
        cbs = event["event"].get("contentBlockStart")
        if cbs is not None and not cbs.get("start"):
            continue
        yield event
    for ui_event in ui.drain():
        shown.append(ui_event)
        yield {"ui": ui_event}
    await asyncio.to_thread(_persist_turn_ui, actor_id, session_id, user_text, shown)


if __name__ == "__main__":
    app.run()
