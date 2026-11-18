"""
Cliente MCP hacia TripPlannerGateway (AgentCore Gateway).

El gateway valida el token con CUSTOM_JWT (Cognito), asi que el orquestador debe presentar
un access token OAuth (flujo M2M / client_credentials):

- Desplegado: AgentCore Identity entrega el token (`@requires_access_token`) usando la
  credencial OAuth `TripPlannerGateway-oauth` que creo `agentcore add gateway`.
- Local: no hay identidad de workload, asi que se pide el token directo al endpoint de
  Cognito con el client id/secret de `agentcore/.env.local`.

Si no hay gateway configurado o no se puede obtener el token, devuelve None y el
orquestador sigue funcionando sin las herramientas del gateway.
"""

import logging
import os

import httpx
from bedrock_agentcore.identity import requires_access_token
from mcp.client.streamable_http import streamablehttp_client
from strands.tools.mcp.mcp_client import MCPClient

logger = logging.getLogger(__name__)

GATEWAY_URL_ENV = "GATEWAY_URL"
DEPLOYED_GATEWAY_URL_ENV = "AGENTCORE_GATEWAY_TRIPPLANNERGATEWAY_URL"
PLACEHOLDER_URL = "https://"

# Nombre de la credencial OAuth gestionada y scope definidos en agentcore.json / Cognito.
OAUTH_PROVIDER_NAME = "TripPlannerGateway-oauth"
OAUTH_SCOPE = "tripplanner-gateway/invoke"

# Solo para ejecucion local (agentcore dev las carga descifradas desde .env.local).
LOCAL_CLIENT_ID_ENV = "AGENTCORE_CREDENTIAL_TRIPPLANNERGATEWAY_OAUTH_CLIENT_ID"
LOCAL_CLIENT_SECRET_ENV = "AGENTCORE_CREDENTIAL_TRIPPLANNERGATEWAY_OAUTH_CLIENT_SECRET"
LOCAL_DISCOVERY_URL_ENV = "GATEWAY_OAUTH_DISCOVERY_URL"


@requires_access_token(provider_name=OAUTH_PROVIDER_NAME, scopes=[OAUTH_SCOPE], auth_flow="M2M")
def _identity_access_token(*, access_token: str) -> str:
    """Obtiene el access token OAuth desde AgentCore Identity."""
    return access_token


def _local_access_token() -> str | None:
    """Pide un token client_credentials directo a Cognito; None si falta configuracion local."""
    client_id = os.getenv(LOCAL_CLIENT_ID_ENV)
    client_secret = os.getenv(LOCAL_CLIENT_SECRET_ENV)
    discovery_url = os.getenv(LOCAL_DISCOVERY_URL_ENV)
    if not (client_id and client_secret and discovery_url):
        return None

    token_url = httpx.get(discovery_url, timeout=10).raise_for_status().json()["token_endpoint"]
    response = httpx.post(
        token_url,
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": OAUTH_SCOPE,
        },
        timeout=10,
    )
    response.raise_for_status()
    return response.json()["access_token"]


def get_gateway_mcp_client() -> MCPClient | None:
    """Devuelve un MCPClient autenticado hacia el gateway, o None si no esta disponible."""
    # Local override first; when deployed, the CLI injects the gateway URL by itself.
    url = os.environ.get(GATEWAY_URL_ENV) or os.environ.get(DEPLOYED_GATEWAY_URL_ENV, "")
    if not url or url == PLACEHOLDER_URL:
        logger.warning("%s no esta configurada: herramientas del gateway no disponibles", GATEWAY_URL_ENV)
        return None

    try:
        token = _local_access_token() or _identity_access_token()
    except Exception:
        logger.exception("No se pudo obtener el token OAuth para el gateway; sigo sin sus herramientas")
        return None

    headers = {"Authorization": f"Bearer {token}"}
    return MCPClient(lambda: streamablehttp_client(url, headers=headers))
