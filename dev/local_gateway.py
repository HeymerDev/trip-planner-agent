"""
Sustituto LOCAL de TripPlannerGateway para probar sin desplegar.

Hace lo que haria el gateway real configurado en agentcore.json:
- Inbound auth CUSTOM_JWT: valida el Bearer token contra el JWKS del emisor OIDC (Cognito),
  y comprueba emisor, cliente permitido y scope, leyendolos de agentcore.json.
- Expone por MCP las herramientas del target TravelTips con el nombre extendido
  "TravelTips___<herramienta>", reutilizando el codigo de app/TravelTips/handler.py.

No reemplaza al gateway de AWS (no usa IAM ni invoca una Lambda real); solo permite ejercitar
el camino Orchestrator -> OAuth -> Gateway -> herramienta en la maquina local.

Uso (con el Python del entorno de OrchestratorAgent, que ya tiene mcp, PyJWT y uvicorn):
    app\\OrchestratorAgent\\.venv\\Scripts\\python.exe dev\\local_gateway.py [--port 8090]
"""

import argparse
import json
import logging
import sys
from pathlib import Path

import httpx
import jwt
import uvicorn
from mcp.server.fastmcp import FastMCP

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app" / "TravelTips"))
import handler  # noqa: E402  (la Lambda real, con datos simulados)

GATEWAY_NAME = "TripPlannerGateway"
TARGET_NAME = "TravelTips"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [local-gateway] %(message)s")
log = logging.getLogger("local-gateway")


def load_gateway_spec() -> dict:
    spec = json.loads((ROOT / "agentcore" / "agentcore.json").read_text(encoding="utf-8"))
    return next(g for g in spec["agentCoreGateways"] if g["name"] == GATEWAY_NAME)


class CustomJwtMiddleware:
    """ASGI middleware que replica el authorizer CUSTOM_JWT del gateway."""

    def __init__(self, app, discovery_url: str, allowed_clients: list[str], allowed_scopes: list[str]):
        discovery = httpx.get(discovery_url, timeout=10).raise_for_status().json()
        self.app = app
        self.issuer = discovery["issuer"]
        self.jwks = jwt.PyJWKClient(discovery["jwks_uri"])
        self.allowed_clients = set(allowed_clients)
        self.allowed_scopes = set(allowed_scopes)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        auth = dict(scope["headers"]).get(b"authorization", b"").decode()
        if not auth.startswith("Bearer "):
            await self._deny(send, "missing bearer token")
            return

        token = auth[len("Bearer "):]
        try:
            key = self.jwks.get_signing_key_from_jwt(token).key
            # Los access tokens de Cognito no traen "aud": se valida client_id y scope.
            claims = jwt.decode(token, key, algorithms=["RS256"], issuer=self.issuer, options={"verify_aud": False})
        except Exception as e:
            await self._deny(send, f"invalid token: {type(e).__name__}")
            return

        if self.allowed_clients and claims.get("client_id") not in self.allowed_clients:
            await self._deny(send, "client_id not allowed")
            return
        token_scopes = set(str(claims.get("scope", "")).split())
        if self.allowed_scopes and not (self.allowed_scopes & token_scopes):
            await self._deny(send, "required scope missing")
            return

        log.info("accepted token client_id=%s scope=%s", claims.get("client_id"), claims.get("scope"))
        await self.app(scope, receive, send)

    async def _deny(self, send, reason: str):
        log.info("denied: %s", reason)
        body = json.dumps({"error": "unauthorized", "reason": reason}).encode()
        await send({"type": "http.response.start", "status": 401,
                    "headers": [(b"content-type", b"application/json"),
                                (b"www-authenticate", b'Bearer realm="TripPlannerGateway"')]})
        await send({"type": "http.response.body", "body": body})


def build_app(port: int):
    gateway = load_gateway_spec()
    jwt_cfg = gateway["authorizerConfiguration"]["customJwtAuthorizer"]
    descriptions = {
        t["name"]: t["description"]
        for tgt in gateway["targets"] if tgt["name"] == TARGET_NAME
        for t in tgt["toolDefinitions"]
    }

    mcp = FastMCP(GATEWAY_NAME, host="127.0.0.1", port=port, stateless_http=True)

    @mcp.tool(name=f"{TARGET_NAME}___get_travel_tips", description=descriptions["get_travel_tips"])
    def get_travel_tips(city: str):
        return handler.TOOLS["get_travel_tips"]({"city": city})

    @mcp.tool(name=f"{TARGET_NAME}___convert_cop_to_usd", description=descriptions["convert_cop_to_usd"])
    def convert_cop_to_usd(amount_cop: float):
        return handler.TOOLS["convert_cop_to_usd"]({"amount_cop": amount_cop})

    return CustomJwtMiddleware(
        mcp.streamable_http_app(),
        discovery_url=jwt_cfg["discoveryUrl"],
        allowed_clients=jwt_cfg.get("allowedClients", []),
        allowed_scopes=jwt_cfg.get("allowedScopes", []),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--port", type=int, default=8090)
    args = parser.parse_args()
    log.info("Local gateway on http://127.0.0.1:%d/mcp (CUSTOM_JWT from agentcore.json)", args.port)
    uvicorn.run(build_app(args.port), host="127.0.0.1", port=args.port, log_level="warning")
