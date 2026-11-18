import os

from strands.models.gemini import GeminiModel
from bedrock_agentcore.identity.auth import requires_api_key

# Must match the credential declared in agentcore.json (agentcore add credential --name Gemini).
IDENTITY_PROVIDER_NAME = "Gemini"
IDENTITY_ENV_VAR = "AGENTCORE_CREDENTIAL_GEMINI"


@requires_api_key(provider_name=IDENTITY_PROVIDER_NAME)
def _agentcore_identity_api_key_provider(api_key: str) -> str:
    """Fetch the API key from AgentCore Identity (Token Vault)."""
    return api_key


def _get_api_key() -> str:
    """Local runs read the key from the environment; deployed runtimes ask AgentCore Identity.

    `agentcore dev` loads agentcore/.env.local (AGENTCORE_CREDENTIAL_GEMINI), and the plain
    `python main.py` flow in dev-all.ps1 exports GEMINI_API_KEY. In a deployed runtime neither
    is set (the key is not stored in agentcore.json), so the Identity provider is used.
    """
    local_key = os.getenv(IDENTITY_ENV_VAR) or os.getenv("GEMINI_API_KEY")
    if local_key:
        return local_key
    return _agentcore_identity_api_key_provider()


def load_model() -> GeminiModel:
    """Get authenticated Gemini model client."""
    return GeminiModel(
        client_args={"api_key": _get_api_key()},
        model_id="gemini-3.5-flash-lite",
    )
