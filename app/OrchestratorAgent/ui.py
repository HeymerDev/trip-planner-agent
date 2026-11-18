"""
Contexto de la peticion y eventos de UI (Agent-Driven UI).

Las Tools publican aqui los datos estructurados (vuelos, clima, viajes, reservas...) y el
entrypoint los mezcla con el stream del modelo como eventos `{"ui": {...}}`. Asi el modelo solo
ve texto compacto y el frontend recibe el JSON completo para pintar componentes.

La identidad del usuario (JWT) vive tambien aqui: las Tools de negocio la reenvian a la API para
que el control de acceso lo haga el backend y nunca el modelo.
"""

import base64
import contextvars
import json
import re
import time
from dataclasses import dataclass, field


@dataclass
class RequestState:
    token: str = ""  # JWT de Cognito del usuario (sin el prefijo "Bearer ")
    user_id: str = ""  # claim `sub` del token (ya verificado por AgentCore Runtime)
    session_id: str = ""
    prompt: str = ""  # ultimo mensaje del usuario en esta peticion
    turn: int = 0  # numero de turno dentro de la sesion
    ui_events: list[dict] = field(default_factory=list)


_current: contextvars.ContextVar[RequestState | None] = contextvars.ContextVar("tripplanner_request", default=None)
# Respaldo: cada sesion de AgentCore corre en su propia microVM, asi que normalmente hay una sola
# peticion activa. Si el contexto no se propaga a la tarea de una Tool, se usa la ultima peticion.
_last: RequestState | None = None

UI_BLOCK = re.compile(r"<ui>(.*?)</ui>", re.DOTALL)


_turns: dict[str, int] = {}


def begin(authorization: str | None, session_id: str = "", prompt: str = "") -> RequestState:
    """Inicia el estado de una peticion a partir de la cabecera Authorization."""
    global _last
    token = (authorization or "").removeprefix("Bearer ").removeprefix("bearer ").strip()
    _turns[session_id] = _turns.get(session_id, 0) + 1
    state = RequestState(
        token=token, user_id=_sub_from_jwt(token), session_id=session_id, prompt=prompt, turn=_turns[session_id]
    )
    _current.set(state)
    _last = state
    return state


def current() -> RequestState:
    return _current.get() or _last or RequestState()


def emit(component: str, data) -> None:
    """Publica un componente para que el frontend lo renderice."""
    current().ui_events.append({"component": component, "data": data})


def drain() -> list[dict]:
    """Devuelve (y vacia) los eventos pendientes."""
    state = current()
    events, state.ui_events = state.ui_events, []
    return events


def extract_ui(text: str) -> tuple[str, list[dict]]:
    """
    Separa los bloques `<ui>{json}</ui>` de la respuesta de un especialista.
    Devuelve (texto sin bloques, lista de {component, data}). Un JSON invalido se descarta.
    """
    events: list[dict] = []
    for match in UI_BLOCK.finditer(text):
        try:
            payload = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and isinstance(payload.get("component"), str) and "data" in payload:
            events.append({"component": payload["component"], "data": payload["data"]})
    return UI_BLOCK.sub("", text).strip(), events


def _sub_from_jwt(token: str) -> str:
    """`sub` del JWT. No se verifica la firma: AgentCore Runtime ya la valido antes de invocar al agente."""
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return str(json.loads(base64.urlsafe_b64decode(payload)).get("sub", ""))
    except Exception:  # noqa: BLE001 - sin token o token ilegible: sin identidad
        return ""


# --------------------------------------------------------------------------------------------
# Barandillas deterministas para acciones con dinero. El modelo de lenguaje no es fiable para
# "pedir confirmacion antes de cobrar", asi que se exige en codigo: una compra solo se ejecuta si
# (1) en un turno ANTERIOR se presento el resumen (primera llamada) y (2) el mensaje actual del
# usuario es afirmativo.

PENDING_TTL_SECONDS = 15 * 60
_pending: dict[str, dict] = {}
AFFIRMATIVE = re.compile(
    r"\b(s[ií]|confirmo|confirmar|confirmad[oa]|acepto|adelante|dale|de acuerdo|ok|okay|claro|hazlo|proceder|procede|"
    r"c[oó]mpralo|comprar|p[aá]galo|pagar|reserva(lo)?)\b",
    re.IGNORECASE,
)
NEGATIVE = re.compile(r"^\s*(no\b|cancela|mejor no|todav[ií]a no)", re.IGNORECASE)
TOPUP_INTENT = re.compile(r"(recarg|abon|deposit|agreg|a[ñn]ad|sum[ae]|cargar|saldo|monedero|dinero|plata)", re.IGNORECASE)


def is_affirmative(text: str) -> bool:
    return bool(text) and bool(AFFIRMATIVE.search(text)) and not NEGATIVE.search(text)


def purchase_gate(trip_id: str, price_cop: int) -> str | None:
    """None = se puede cobrar. Si no, devuelve el mensaje que el modelo debe usar (no se cobro nada)."""
    state = current()
    key = state.session_id or state.user_id or "anon"
    pending = _pending.get(key)
    if (
        pending
        and pending["turn"] < state.turn
        and pending["trip_id"] == trip_id
        and pending["price"] == price_cop
        and time.time() - pending["at"] < PENDING_TTL_SECONDS
        and is_affirmative(state.prompt)
    ):
        _pending.pop(key, None)
        return None
    if not (pending and pending["turn"] == state.turn):
        _pending[key] = {"trip_id": trip_id, "price": price_cop, "turn": state.turn, "at": time.time()}
    return json.dumps(
        {
            "status": "CONFIRMATION_REQUIRED",
            "charged": False,
            "message": (
                "NO SE COBRO NADA. Muestra al usuario el resumen de la compra (que compra, precio total en COP y su saldo) "
                "y preguntale si confirma. Cuando el usuario responda afirmativamente en su SIGUIENTE mensaje, vuelve a llamar "
                "a create_reservation con exactamente los mismos argumentos."
            ),
        },
        ensure_ascii=False,
    )


def topup_allowed() -> bool:
    """Recargar solo si el mensaje actual del usuario habla de recargar/agregar saldo."""
    return bool(TOPUP_INTENT.search(current().prompt or ""))


# Enlaces que realmente entregaron los especialistas en cada sesion. El modelo a veces inventa URLs
# (por ejemplo "booking.com"); solo se guardan en una reserva las que vienen de un especialista.
_links: dict[str, set[str]] = {}
URL_PATTERN = re.compile(r"""https?://[^\s)"'<>\]\\]+""")


def _clean_url(url: str) -> str:
    return url.rstrip(".,;:!?")


def remember_links(text: str) -> None:
    key = current().session_id or current().user_id or "anon"
    found = {_clean_url(u) for u in URL_PATTERN.findall(text or "")}
    if found:
        _links.setdefault(key, set()).update(found)


def known_link(url: str) -> bool:
    key = current().session_id or current().user_id or "anon"
    return _clean_url(url or "") in _links.get(key, set())
