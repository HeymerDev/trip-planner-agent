"""
WeatherAgent - Agente A2A que entrega el clima REAL con el MCP `mcp-weather-server` (Open-Meteo).

Las herramientas las expone el paquete de PyPI `mcp-weather-server`, que este agente lanza como
subproceso (stdio) con el mismo Python del entorno: no necesita Node ni servicios externos
(solo Open-Meteo, sin API key) y viaja como una dependencia mas dentro de un runtime Python.
"""

import os
import sys
from datetime import date

from mcp import StdioServerParameters
from mcp.client.stdio import stdio_client
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

# The server logs every request at INFO to stderr; keep it out of this agent's console.
_DEVNULL = open(os.devnull, "w")

# The package also ships air-quality and timezone tools; a trip-weather agent only needs these two.
WEATHER_TOOLS = ["get_current_weather", "get_weather_byDateTimeRange"]

SYSTEM_PROMPT = """
Eres un agente especializado en el clima para planear viajes. Hoy es {today}.
Tus herramientas vienen del servicio mcp-weather-server (Open-Meteo):
- get_current_weather: condiciones actuales de una ciudad.
- get_weather_byDateTimeRange: datos horarios entre dos fechas (start_date y
  end_date en AAAA-MM-DD).

Reglas:
- El nombre de la ciudad va en ingles y con el pais, por ejemplo "Cartagena,
  Colombia" o "Medellin, Colombia".
- El pronostico real solo llega a unos 16 dias desde hoy. Si la fecha pedida esta
  mas lejos, o es una fecha pasada, dilo con claridad y no inventes un pronostico.
- Pide un solo dia por llamada (start_date igual a end_date): cada dia trae datos
  horarios muy largos. Si el viaje abarca varios dias, haz una llamada por dia
  (maximo 4 dias; si piden mas, resume los primeros 4 y avisalo).
- Con los datos horarios, resume tu mismo cada dia: temperatura minima y maxima,
  condiciones predominantes (cielo, lluvia), probabilidad maxima de lluvia y
  humedad aproximada. No pegues los datos horarios en la respuesta.
- No inventes datos que las herramientas no devuelvan.
Responde en espanol, de forma clara y concisa.

SALIDA ESTRUCTURADA (para que la aplicacion muestre tarjetas por dia): SOLO si obtuviste datos reales,
termina tu respuesta con UN bloque en una sola linea, sin markdown alrededor:
<ui>{{"component":"weather","data":{{"city":"Cartagena, Colombia","days":[{{"date":"AAAA-MM-DD","minC":25.3,"maxC":28.9,"condition":"Nublado con lloviznas","rainProbability":78,"humidity":88,"icon":"rain"}}]}}}}</ui>
Un elemento por dia consultado. icon = sun|partly|cloud|rain|storm|fog|snow. Campo desconocido = null.
El JSON debe ser valido. Si la fecha esta fuera del horizonte del pronostico, no incluyas el bloque.
"""


def _weather_mcp_client() -> MCPClient:
    params = StdioServerParameters(command=sys.executable, args=["-m", "mcp_weather_server"])
    return MCPClient(
        lambda: stdio_client(params, errlog=_DEVNULL),
        tool_filters={"allowed": WEATHER_TOOLS},
    )


def create_agent(context_id: str) -> Agent:
    """Fabrica que crea una instancia del agente de clima por contexto de conversacion."""
    session_manager = None
    if MEMORY_ID and MEMORY_ID != "PENDING_MEMORY_ID":
        session_manager = AgentCoreMemorySessionManager(
            agentcore_memory_config=AgentCoreMemoryConfig(
                memory_id=MEMORY_ID,
                session_id=context_id,
                actor_id="WeatherAgent",
            ),
        )
    return Agent(
        model=load_model(),
        system_prompt=SYSTEM_PROMPT.format(today=date.today().isoformat()),
        tools=[_weather_mcp_client()],
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
