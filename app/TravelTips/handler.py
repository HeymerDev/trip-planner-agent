"""
Lambda de herramientas para TripPlannerGateway (datos simulados, sin APIs externas).

AgentCore Gateway invoca esta funcion una vez por llamada a herramienta y pasa el
nombre extendido en context.client_context.custom["bedrockAgentCoreToolName"],
con el formato "{target}___{herramienta}". Los argumentos de la herramienta llegan
como el propio `event`.
"""
import json
import logging
from typing import Any, Callable, Dict

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Misma tasa que usan los precios simulados de FlightsAgent / HotelsAgent.
COP_PER_USD = 4000

TIPS = {
    "bogota": {
        "city": "Bogota",
        "weather": "Fresco todo el ano (alrededor de 14 C); lleva chaqueta y paraguas.",
        "transport": "TransMilenio y taxis por aplicacion; evita las horas pico.",
        "highlights": "La Candelaria, Museo del Oro, Monserrate.",
    },
    "medellin": {
        "city": "Medellin",
        "weather": "Clima templado (alrededor de 23 C) casi todo el ano.",
        "transport": "Metro y Metrocable; es la forma mas comoda de moverse.",
        "highlights": "Comuna 13, Parque Arvi, El Poblado.",
    },
    "cartagena": {
        "city": "Cartagena",
        "weather": "Calor y humedad altos (alrededor de 31 C); protector solar y ropa ligera.",
        "transport": "Caminar por el centro amurallado; taxis para ir a Bocagrande o las islas.",
        "highlights": "Ciudad Amurallada, Castillo San Felipe, Islas del Rosario.",
    },
    "barranquilla": {
        "city": "Barranquilla",
        "weather": "Calido (alrededor de 30 C); lo mas fresco es entre diciembre y marzo.",
        "transport": "Taxis y transporte por aplicacion; Transmetro para trayectos largos.",
        "highlights": "Malecon del Rio, Carnaval (febrero), Museo del Caribe.",
    },
}

TOOLS: Dict[str, Callable[[Dict[str, Any]], Any]] = {}


def tool(name: str):
    """Registra una funcion como herramienta del gateway."""

    def decorator(func):
        TOOLS[name] = func
        return func

    return decorator


def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """Enruta la llamada del gateway a la herramienta correspondiente."""
    try:
        client_context = getattr(context, "client_context", None)
        custom = (getattr(client_context, "custom", None) or {}) if client_context else {}
        extended_name = custom.get("bedrockAgentCoreToolName", "")
        tool_name = extended_name.split("___", 1)[1] if "___" in extended_name else None

        if not tool_name:
            return _response(400, {"error": "Falta el nombre de la herramienta en bedrockAgentCoreToolName"})

        handler = TOOLS.get(tool_name)
        if not handler:
            return _response(400, {"error": f"Herramienta desconocida: {tool_name}"})

        return _response(200, {"result": handler(event)})

    except Exception as e:
        logger.exception("Fallo la ejecucion de la herramienta")
        return _response(500, {"error": str(e)})


def _response(status_code: int, body: Dict[str, Any]) -> Dict[str, Any]:
    return {"statusCode": status_code, "body": json.dumps(body, ensure_ascii=False)}


@tool("get_travel_tips")
def get_travel_tips(event: Dict[str, Any]) -> Any:
    """Devuelve consejos de viaje (clima, transporte, lugares) para una ciudad colombiana."""
    city = str(event.get("city", "")).strip()
    if not city:
        return "Falta el parametro requerido: city"

    key = city.lower().replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")
    tips = TIPS.get(key)
    if not tips:
        return f"No hay consejos para '{city}'. Ciudades disponibles: {', '.join(t['city'] for t in TIPS.values())}."
    return tips


@tool("convert_cop_to_usd")
def convert_cop_to_usd(event: Dict[str, Any]) -> Any:
    """Convierte un monto de pesos colombianos (COP) a dolares (USD) con una tasa fija simulada."""
    try:
        amount_cop = float(event["amount_cop"])
    except (KeyError, TypeError, ValueError):
        return "Falta o es invalido el parametro requerido: amount_cop (numero)"

    return {
        "amount_cop": amount_cop,
        "rate_cop_per_usd": COP_PER_USD,
        "amount_usd": round(amount_cop / COP_PER_USD, 2),
    }
