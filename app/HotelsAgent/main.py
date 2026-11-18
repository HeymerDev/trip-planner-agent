"""
HotelsAgent - Agente A2A que busca hospedaje REAL con el MCP publico de Staylist World.

Las herramientas (search_hotels, get_hotel, get_booking_link, list_destinations) las expone el
servidor MCP remoto https://staylist.world/mcp (gratuito, sin registro ni API key); este agente
solo las conecta a Gemini y a la memoria. Sobrescribible con la variable HOTELS_MCP_URL.
"""

import os

from mcp.client.streamable_http import streamablehttp_client
from strands import Agent, ModelRetryStrategy
from strands.multiagent.a2a.executor import StrandsA2AExecutor
from strands.tools.mcp.mcp_client import MCPClient
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
MEMORY_ID = os.environ.get("MEMORY_ID") or os.environ.get("MEMORY_TRIPPLANNERMEMORY_ID", "")
HOTELS_MCP_URL = os.environ.get("HOTELS_MCP_URL", "https://staylist.world/mcp")

SYSTEM_PROMPT = """
Eres un agente especializado en busqueda de hospedaje. Tus herramientas vienen
del servicio Staylist World:
- search_hotels: busca y compara hoteles por ciudad. Para ciudades de Colombia
  usa country_code "CO". Pasa checkin y checkout (AAAA-MM-DD) solo si el usuario
  dio las dos fechas.
- get_hotel: detalles de un hotel; necesita el hotel_id exacto que devolvio
  search_hotels.
- get_booking_link: enlaces de reserva de un hotel; conserva las URL sin
  modificarlas. No puedes reservar ni cobrar: el viajero completa la reserva en
  el sitio de destino.
- list_destinations: destinos populares.

Reglas: un campo vacio significa desconocido, no malo. Los precios son valores
observados antes, no en vivo: aclaralo al presentarlos. No inventes datos que las
herramientas no devuelvan. Responde en espanol, de forma clara y concisa.

SALIDA ESTRUCTURADA (para que la aplicacion muestre tarjetas): SOLO si obtuviste hoteles de la
herramienta, termina tu respuesta con UN bloque en una sola linea, sin markdown alrededor:
<ui>{"component":"hotels","data":{"city":"Cartagena","checkin":"AAAA-MM-DD","checkout":"AAAA-MM-DD","hotels":[{"name":"Hotel X","area":"Centro historico","stars":4,"rating":9.1,"pricePerNight":692,"currency":"USD","highlights":["piscina","desayuno"],"bookingLinks":[{"label":"Trip.com","url":"https://..."}]}]}}</ui>
Hasta 5 hoteles con datos reales (campo desconocido = null, checkin/checkout = null si no los dieron) y
URLs copiadas sin modificar. El JSON debe ser valido. Si no hay resultados, no incluyas el bloque.
"""


def _hotels_mcp_client() -> MCPClient:
    return MCPClient(lambda: streamablehttp_client(HOTELS_MCP_URL))


def create_agent(context_id: str) -> Agent:
    """Fabrica que crea una instancia del agente de hospedaje por contexto de conversacion."""
    session_manager = None
    if MEMORY_ID and MEMORY_ID != "PENDING_MEMORY_ID":
        session_manager = AgentCoreMemorySessionManager(
            agentcore_memory_config=AgentCoreMemoryConfig(
                memory_id=MEMORY_ID,
                session_id=context_id,
                actor_id="HotelsAgent",
            ),
        )
    return Agent(
        model=load_model(),
        system_prompt=SYSTEM_PROMPT,
        tools=[_hotels_mcp_client()],
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
