"""
FlightsAgent - Agente A2A que busca vuelos REALES con el MCP de FlightPowers (Google Flights).

Las herramientas (search_oneway_flights, search_roundtrip_flights) las expone el servidor MCP
remoto https://flights.flightpowers.com/mcp. Listar herramientas no pide credenciales, pero
ejecutar una busqueda si: una clave de RapidAPI (FLIGHTS_RAPIDAPI_KEY, cabecera x-rapidapi-key) o
un token de conexion de FlightPowers (FLIGHTS_MCP_TOKEN, cabecera Authorization: Bearer fpk_...).
"""

import logging
import os
from datetime import date

from mcp.client.streamable_http import streamablehttp_client
from strands import Agent, ModelRetryStrategy
from strands.multiagent.a2a.executor import StrandsA2AExecutor
from strands.tools.mcp.mcp_client import MCPClient
from bedrock_agentcore.identity.auth import requires_api_key
from bedrock_agentcore.runtime import serve_a2a
from bedrock_agentcore.memory.integrations.strands.config import AgentCoreMemoryConfig
from bedrock_agentcore.memory.integrations.strands.session_manager import AgentCoreMemorySessionManager
from model.load import load_model

# strands.telemetry.tracer unconditionally calls ThreadingInstrumentor().instrument(),
# which has a known upstream bug: it attaches an OTEL context token on one thread/task
# and can detach it from a different one (contextvars "Token was created in a different
# Context" ValueError), crashing mid-conversation. Tracing doesn't need cross-thread
# context propagation here, so disable it before strands gets a chance to apply it.
from opentelemetry.instrumentation.threading import ThreadingInstrumentor

ThreadingInstrumentor.instrument = lambda self, **kwargs: None

# Local override first; when deployed, the CLI injects MEMORY_<NAME>_ID for the memory it created.
logger = logging.getLogger(__name__)

MEMORY_ID = os.environ.get("MEMORY_ID") or os.environ.get("MEMORY_TRIPPLANNERMEMORY_ID", "")
FLIGHTS_MCP_URL = os.environ.get("FLIGHTS_MCP_URL", "https://flights.flightpowers.com/mcp")

SYSTEM_PROMPT = """
Eres un agente especializado en busqueda de vuelos. Hoy es {today}. Tus
herramientas vienen del servicio FlightPowers (tarifas en vivo de Google Flights):
- search_oneway_flights: vuelos solo de ida.
- search_roundtrip_flights: ida y vuelta; acepta fecha de regreso o numero de noches.

Reglas:
- Usa codigos IATA (por ejemplo Bogota BOG, Medellin MDE, Cartagena CTG,
  Barranquilla BAQ). Cada busqueda admite un solo origen; varios destinos se
  pasan juntos separados por coma.
- Cada resultado trae el rango historico de precios de Google (bajo / tipico /
  alto): usalo para decir si la tarifa es buena. Incluye el enlace de compra
  (buy_link) sin modificarlo; no puedes reservar.
- Las tarifas son en vivo y caducan en minutos: no reutilices un resultado viejo.
- Si la herramienta responde que falta una clave (needs_api_key), que se agoto la
  prueba (trial_exhausted) o devuelve un error, explicaselo al usuario tal cual.
  Nunca inventes vuelos, precios ni horarios.
Responde en espanol, de forma clara y concisa.

SALIDA ESTRUCTURADA (para que la aplicacion muestre tarjetas): SOLO si obtuviste vuelos de la
herramienta, termina tu respuesta con UN bloque en una sola linea, sin markdown alrededor:
<ui>{{"component":"flights","data":{{"origin":"BOG","destination":"CTG","departDate":"AAAA-MM-DD","returnDate":null,"currency":"USD","flights":[{{"airline":"LATAM","departure":"19:40","arrival":"21:10","duration":"1 h 30 min","stops":0,"price":102,"currency":"USD","priceLevel":"low","buyLink":"https://..."}}]}}}}</ui>
Incluye hasta 6 vuelos con datos reales devueltos por la herramienta (campo desconocido = null,
priceLevel = low|typical|high o null) y buyLink copiado sin modificar. El JSON debe ser valido.
Si no hay vuelos o la herramienta fallo, no incluyas el bloque.
"""


# Must match the credential declared in agentcore.json (agentcore add credential --name FlightPowers).
IDENTITY_PROVIDER_NAME = "FlightPowers"
IDENTITY_ENV_VAR = "AGENTCORE_CREDENTIAL_FLIGHTPOWERS"


@requires_api_key(provider_name=IDENTITY_PROVIDER_NAME)
def _identity_rapidapi_key(api_key: str) -> str:
    """Fetch the RapidAPI key from AgentCore Identity (Token Vault)."""
    return api_key


def _auth_headers() -> dict[str, str]:
    """Credencial para ejecutar busquedas; vacia si no hay ninguna configurada.

    Local: variables de entorno (`agentcore dev` carga AGENTCORE_CREDENTIAL_FLIGHTPOWERS desde
    .env.local; `dev-all.ps1` exporta FLIGHTS_RAPIDAPI_KEY). Desplegado: no hay ninguna, asi que
    se pide a AgentCore Identity, donde esta la credencial FlightPowers.
    """
    rapidapi_key = os.environ.get("FLIGHTS_RAPIDAPI_KEY") or os.environ.get(IDENTITY_ENV_VAR)
    if rapidapi_key:
        return {"x-rapidapi-key": rapidapi_key}
    if token := os.environ.get("FLIGHTS_MCP_TOKEN"):
        return {"Authorization": f"Bearer {token}"}
    try:
        return {"x-rapidapi-key": _identity_rapidapi_key()}
    except Exception:
        logger.warning("Sin credencial de FlightPowers (ni en el entorno ni en AgentCore Identity)", exc_info=True)
        return {}


MISSING_CREDENTIAL_NOTE = """
AVISO: el servicio de vuelos NO esta configurado (falta la credencial de FlightPowers:
FLIGHTS_RAPIDAPI_KEY o FLIGHTS_MCP_TOKEN). No tienes herramientas de busqueda. Si te piden
vuelos, explica que no puedes consultarlos hasta que se configure esa credencial y no
inventes vuelos, precios ni horarios.
"""


def _flights_mcp_client(headers: dict[str, str]) -> MCPClient:
    return MCPClient(lambda: streamablehttp_client(FLIGHTS_MCP_URL, headers=headers))


def create_agent(context_id: str) -> Agent:
    """Fabrica que crea una instancia del agente de vuelos por contexto de conversacion."""
    session_manager = None
    if MEMORY_ID and MEMORY_ID != "PENDING_MEMORY_ID":
        session_manager = AgentCoreMemorySessionManager(
            agentcore_memory_config=AgentCoreMemoryConfig(
                memory_id=MEMORY_ID,
                session_id=context_id,
                actor_id="FlightsAgent",
            ),
        )
    # Without a credential FlightPowers answers tools/call with a 401 OAuth challenge that the MCP
    # client doesn't handle, so the call just hangs. Don't offer the tools; say so in the prompt.
    headers = _auth_headers()
    system_prompt = SYSTEM_PROMPT.format(today=date.today().isoformat())
    if headers:
        tools = [_flights_mcp_client(headers)]
    else:
        tools = []
        system_prompt += MISSING_CREDENTIAL_NOTE
    return Agent(
        model=load_model(),
        system_prompt=system_prompt,
        tools=tools,
        session_manager=session_manager,
        # Gemini's lite/preview models return transient 503s under load more often
        # than the default retry budget (6 attempts, ~2min) tolerates. Give it more
        # room before giving up.
        retry_strategy=ModelRetryStrategy(max_attempts=10, initial_delay=5, max_delay=60),
        # This agent is served over A2A, not an interactive console, so the default
        # PrintingCallbackHandler's per-token print() is both useless and a crash
        # risk: it raises UnicodeEncodeError on Windows' cp1252 console for any
        # response containing characters outside that codepage, which then corrupts
        # OTEL's span-context stack during the generator's teardown.
        callback_handler=None,
    )


if __name__ == "__main__":
    serve_a2a(StrandsA2AExecutor(agent_factory=create_agent))
