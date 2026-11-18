# Diseño técnico — TripPlanner AI

> Responde a `requirements.md`. Cada sección indica los requisitos que cubre entre corchetes.

## 1. Visión general

```
                    ┌────────────────────────────────────────────┐
                    │  Navegador (React + Vite) — S3 + CloudFront │
                    └───────┬─────────────────────────┬──────────┘
        JWT de Cognito      │ CANAL 1 (REST/JSON)     │ CANAL 2 (HTTP streaming, SSE)
                            ▼                         ▼
                  ┌──────────────────┐     ┌──────────────────────────────┐
                  │ API Gateway HTTP │     │ Amazon Bedrock AgentCore     │
                  │ authorizer JWT   │     │ Runtime: OrchestratorAgent   │
                  └────────┬─────────┘     │ (authorizer JWT de Cognito)  │
                           ▼               └──┬──────────┬──────────┬─────┘
                  ┌──────────────────┐        │ A2A      │ A2A      │ A2A  (SigV4)
                  │ Lambdas negocio  │◄───────┘     ┌────▼───┐ ┌────▼───┐ ┌▼──────┐
                  │ (Tools de negocio│  HTTPS + JWT │Flights │ │Weather │ │Hotels │
                  │  y pantallas)    │  del usuario │ + MCP  │ │ + MCP  │ │ + MCP │
                  └────────┬─────────┘              └────────┘ └────────┘ └───────┘
                           ▼
                  ┌──────────────────┐
                  │ DynamoDB (tabla  │   Memoria de AgentCore (conversación) — NO es fuente de verdad
                  │ única)           │
                  └──────────────────┘
```

**Decisión D-01 — Dos canales independientes** [RNF-02]. El chat va directo del navegador a AgentCore
(el endpoint ya admite CORS y *streaming*), sin API Gateway. Las pantallas de negocio van por
API Gateway.

**Decisión D-02 — Las Tools de negocio llaman a la misma API que el frontend** [RF-90..97, RNF-13].
Cada Tool del Orchestrator realiza una petición HTTPS a API Gateway reenviando el **JWT del usuario**.
Así existe un solo conjunto de Lambdas (lógica y validaciones únicas), el agente y la UI quedan
sujetos al mismo control de acceso, y la identidad nunca la decide el modelo.
Alternativa descartada: Lambdas separadas por canal (duplica validaciones) y usar AgentCore Gateway con
Lambda target (la Lambda no recibe la identidad del usuario final de forma directa).

**Decisión D-03 — Autenticación con Amazon Cognito** [RF-01, RNF-17]. Un User Pool compartido:
API Gateway valida el *access token* con un autorizador JWT nativo, y el runtime del Orchestrator se
configura con `customJWTAuthorizer` sobre el mismo pool. El registro se auto-confirma con un *trigger*
PreSignUp para que la demostración no dependa del correo electrónico.

**Decisión D-04 — Una sola tabla DynamoDB** [RF-03..RF-64]. Ver §3.

**Decisión D-05 — Agent-Driven UI mediante eventos del stream** [RF-13]. El Orchestrator emite,
además de texto, eventos `ui` con datos estructurados que el frontend convierte en componentes (§6).

## 2. Componentes

| Componente | Tecnología | Responsabilidad |
|---|---|---|
| Frontend | React 18 + Vite + React Router | UX, sesión Cognito, consumo de ambos canales |
| Hosting | S3 privado + CloudFront (OAC) | Publicación HTTPS del frontend |
| Auth | Cognito User Pool + App Client público (SRP) | Registro/login, emisión de JWT |
| API | API Gateway HTTP API | Exposición REST, autorizador JWT, CORS, *throttling* |
| Lambdas | Python 3.12 | Lógica de negocio y validación (§5) |
| Datos | DynamoDB on-demand, tabla única | Fuente de verdad |
| Orchestrator | Strands + AgentCore Runtime (HTTP) | Interpreta, decide, delega, usa Tools |
| Flights / Weather / Hotels | Strands + A2A + MCP | Especialistas |
| Memoria | AgentCore Memory (3 estrategias) | Contexto conversacional, preferencias |
| IaC | AWS SAM (backend) + AgentCore CLI (agentes) | Despliegue repetible |

## 3. Modelo de datos [RNF-06, RNF-13]

### 3.1 Tabla única `tripplanner-main`

Clave de partición `PK` (S) y de ordenación `SK` (S). Facturación bajo demanda, cifrado en reposo,
*point-in-time recovery* activado.

| Entidad | PK | SK | Atributos |
|---|---|---|---|
| Perfil | `USER#<sub>` | `PROFILE` | `email`, `name`, `createdAt` |
| Preferencias | `USER#<sub>` | `PREFS` | `defaultBudgetCOP`, `activities[]`, `airlines[]`, `restrictions`, `updatedAt` |
| Monedero | `USER#<sub>` | `WALLET` | `balanceCOP` (N), `updatedAt` |
| Movimiento | `USER#<sub>` | `TXN#<ISO-ts>#<id>` | `type` (`TOPUP`/`PURCHASE`/`REFUND`), `amountCOP` (negativo en compras), `title`, `reservationId?`, `createdAt` |
| Viaje | `USER#<sub>` | `TRIP#<tripId>` | `name`, `origin`, `destination`, `startDate`, `endDate`, `travelers`, `budgetCOP`, `status`, `notes`, `createdAt`, `updatedAt` |
| Itinerario | `USER#<sub>` | `ITIN#<tripId>` | `days[]` (`date`, `items[]` con `time`, `title`, `place`, `costCOP`, `notes`), `updatedAt` |
| Reserva | `USER#<sub>` | `RES#<resId>` | `tripId`, `kind` (`FLIGHT`/`HOTEL`/`ACTIVITY`), `title`, `details{}`, `priceCOP`, `originalPrice?`, `originalCurrency?`, `fxRate?`, `status`, `paid` (bool), `link?`, `createdAt`, `updatedAt` |

### 3.2 Justificación del diseño de claves
- **Aislamiento por usuario por construcción:** todo ítem cuelga de `USER#<sub>` y el `sub` se toma del
  token verificado. Ninguna consulta puede cruzar usuarios porque la clave de partición nunca viene del cliente.
- **Patrones de acceso resueltos con `Query` (sin `Scan`):**

| Patrón | Operación |
|---|---|
| Listar viajes | `Query PK=USER#u AND begins_with(SK,'TRIP#')` |
| Obtener viaje / itinerario | `GetItem` con `SK=TRIP#id` / `ITIN#id` |
| Listar reservas | `Query ... begins_with(SK,'RES#')` |
| Reservas de un viaje | misma consulta con `FilterExpression tripId = :t` |
| Historial del monedero | `Query ... begins_with(SK,'TXN#')`, `ScanIndexForward=false` |
| Dashboard | 3 `Query` (viajes, reservas, monedero) |

- **Reserva con `SK=RES#<id>` y `tripId` como atributo** (en lugar de anidarla bajo el viaje): permite
  reasociar una reserva a otro viaje [RF-54] con un simple `UpdateItem`, y el volumen por usuario es pequeño,
  por lo que el filtro es suficiente. Un GSI sería prematuro.
- **Itinerario como un único ítem** con la lista de días: se lee y reemplaza de forma atómica; el tamaño
  esperado (decenas de actividades) queda muy por debajo del límite de 400 KB.
- **Dinero como entero en COP** (sin decimales) para evitar errores de coma flotante.

### 3.3 Estados de reserva [RF-52]
`SIMULADA` (por defecto) → `PENDIENTE` → `CONFIRMADA` (reservado para proveedores reales) y `CANCELADA`.
Transiciones permitidas: `SIMULADA|PENDIENTE → CONFIRMADA|CANCELADA`, `SIMULADA ↔ PENDIENTE`.
`CANCELADA` y `CONFIRMADA` son terminales para el sistema simulado.

## 4. API REST (Canal 1) [RNF-14, RNF-15]

Base: `https://<api-id>.execute-api.us-east-2.amazonaws.com`. Todas las rutas exigen
`Authorization: Bearer <access token>`. Respuestas JSON; errores: `{"error": {"code", "message", "fields?"}}`.

| Método y ruta | Lambda | Tool | Descripción |
|---|---|---|---|
| `GET/PUT /me` | `me` | — | Perfil (se crea en el primer acceso) |
| `GET/PUT /me/preferences` | `me` | — | Preferencias |
| `GET /dashboard` | `me` | — | Próximos viajes, reservas recientes, saldo |
| `POST /trips` | `trips` | `create_trip` | Crear viaje |
| `GET /trips` | `trips` | `get_trips` | Listar |
| `GET /trips/{id}` | `trips` | `get_trips` | Detalle (incluye itinerario y resumen de presupuesto) |
| `PATCH /trips/{id}` | `trips` | `update_trip` | Actualizar |
| `DELETE /trips/{id}` | `trips` | — | Eliminar (y su itinerario; reservas quedan sin viaje) |
| `POST /trips/{id}/itinerary` | `itineraries` | `create_itinerary` | Crear (409 si existe) |
| `PUT /trips/{id}/itinerary` | `itineraries` | `update_itinerary` | Reemplazar/modificar |
| `GET /trips/{id}/itinerary` | `itineraries` | — | Consultar |
| `POST /reservations` | `reservations` | `create_reservation` | Registrar (sin cobro) |
| `GET /reservations?tripId=` | `reservations` | `get_reservations` | Listar |
| `GET /reservations/{id}` | `reservations` | `get_reservations` | Detalle |
| `PATCH /reservations/{id}` | `reservations` | `update_reservation` | Editar, cambiar estado, reasociar, cancelar (reembolsa) |
| `GET /wallet` | `wallet` | `get_wallet` | Saldo y movimientos |
| `POST /wallet/topup` | `wallet` | `top_up_wallet` | Recarga simulada |
| `POST /purchases` | `wallet` | `create_reservation` (con `pay=true`) | Compra atómica |
| `GET/DELETE /conversations[/{id}]` | `conversations` | — | Historial leído/eliminado de la memoria del agente |
| `GET /fx` | `utils` | `convert_currency` | Tasa de cambio (open.er-api.com) |
| `GET /transport` | `utils` | `compare_transport` | Bus vs. avión puerta a puerta |

Códigos: `200/201` éxito · `400` validación · `401` sin/ inválido token · `404` no existe o es de otro
usuario · `409` conflicto (itinerario existente, saldo insuficiente, clave de idempotencia repetida,
transición inválida) · `429` *throttling* · `500` error interno genérico (detalle solo en logs).

### 4.1 Validaciones principales [RNF-12]
| Campo | Regla |
|---|---|
| `name`, `title` | 1–120 caracteres |
| `origin`, `destination` | 2–80 caracteres |
| `startDate`, `endDate` | `YYYY-MM-DD` válidas, `endDate >= startDate`, viaje ≤ 90 días |
| `travelers` | entero 1–20 |
| `budgetCOP`, `priceCOP` | entero 0–1 000 000 000 |
| `kind` | `FLIGHT` \| `HOTEL` \| `ACTIVITY` |
| `status` | enum y transición permitida (§3.3) |
| `topup.amountCOP` | entero 1 000–10 000 000 |
| itinerario | ≤ 31 días, ≤ 20 actividades por día, `time` `HH:MM`, fechas dentro del viaje |
| `tripId` en reserva | debe existir y pertenecer al usuario |
| cuerpo | JSON ≤ 64 KB; campos desconocidos se ignoran |

### 4.2 Compra atómica e idempotente [RF-61..65, RNF-20]
`POST /purchases` ejecuta una `TransactWriteItems` con tres operaciones: (1) `Update WALLET` con
`ConditionExpression balanceCOP >= :price`, (2) `Put RES#id` con `attribute_not_exists(PK)`, (3) `Put TXN#...`.
El `resId` se deriva de `idempotencyKey` (SHA-256 truncado) si se envía; un reintento choca con la condición del
punto (2) y responde `409 DUPLICATE` sin descontar de nuevo. Cancelar una reserva pagada ejecuta otra
transacción que marca `CANCELADA`, acredita el saldo y crea el `TXN` de tipo `REFUND`, con condición
`status <> CANCELADA` para impedir doble reembolso.

## 5. Lambdas e IAM [RNF-10]

| Lambda | Rutas | Permisos DynamoDB (solo sobre la tabla) |
|---|---|---|
| `me` | `/me*`, `/dashboard` | `GetItem`, `PutItem`, `UpdateItem`, `Query` |
| `trips` | `/trips`, `/trips/{id}` | `GetItem`, `PutItem`, `UpdateItem`, `DeleteItem`, `Query` |
| `itineraries` | `/trips/{id}/itinerary` | `GetItem`, `PutItem`, `UpdateItem` |
| `reservations` | `/reservations*` | `GetItem`, `PutItem`, `UpdateItem`, `Query` (el reembolso usa transacción) |
| `wallet` | `/wallet*`, `/purchases` | `GetItem`, `PutItem`, `UpdateItem`, `Query` (las transacciones exigen `PutItem`/`UpdateItem`: IAM no tiene una acción `TransactWriteItems`) |
| `utils` | `/fx`, `/transport` | ninguno (no tiene acceso a la tabla) |
| `presignup` | trigger Cognito | ninguno |

Cada función recibe un rol propio generado por SAM con esas acciones y los permisos de logs. El código común
(`common.py`: respuesta HTTP, validación, acceso a tabla, extracción del `sub`) se empaqueta con cada función.

**Rol del Orchestrator:** `bedrock-agentcore:InvokeAgentRuntime` y `GetAgentCard` solo sobre los runtimes
`tripplanner_*`; memoria; credenciales de AgentCore Identity. **No** tiene permisos sobre DynamoDB: solo puede
operar el negocio a través de la API con el token del usuario.

## 6. Canal agéntico [RF-10..14, RF-13]

### 6.1 Invocación desde el navegador
```
POST https://bedrock-agentcore.us-east-2.amazonaws.com/runtimes/<ARN codificado>/invocations?qualifier=DEFAULT
Authorization: Bearer <access token Cognito>
X-Amzn-Bedrock-AgentCore-Runtime-Session-Id: <uuid ≥ 33 caracteres, = id de conversación>
Content-Type: application/json
{"prompt": "..."}
```
El runtime valida el JWT (`customJWTAuthorizer`: discovery URL del pool + `allowedClients`) y reenvía la cabecera
`Authorization` al código del agente (`requestHeaderAllowlist`). El agente decodifica el `sub` para usarlo como
`actor_id` de la memoria y reenvía el token a la API de negocio.

### 6.2 Protocolo de eventos (SSE, una línea `data: {json}` por evento)
| Evento | Forma | Uso en la UI |
|---|---|---|
| Texto | `{"event":{"contentBlockDelta":{"delta":{"text":"…"}}}}` | Se concatena en la burbuja del asistente |
| Herramienta | `{"event":{"contentBlockStart":{"start":{"toolUse":{"name":"ask_flights"}}}}}` | Indicador "Consultando vuelos…" |
| UI | `{"ui":{"component":"flights","data":{…}}}` | Se renderiza un componente |
| Fin / error | `{"event":{"messageStop":…}}` / `{"error":"…"}` | Cierra la burbuja |

### 6.3 Componentes dirigidos por agentes
| `component` | Origen | Componente visual |
|---|---|---|
| `flights` | Flights Agent (JSON estructurado) | Tarjetas comparativas |
| `weather` | Weather Agent | Tarjetas por día |
| `hotels` | Hotels Agent | Tarjetas de hotel con enlace |
| `trip`, `trips` | Tools de viajes | Tarjetas de viaje |
| `itinerary` | Tools de itinerario | Agenda por día |
| `reservation`, `reservations` | Tools de reservas | Lista con estado |
| `wallet` | Tools de monedero | Saldo y movimientos |
| `currency`, `transport` | Tools extra | Conversión / comparación bus-avión |

**Mecanismo.** Los especialistas terminan su respuesta con un bloque `<ui>{json}</ui>`. La Tool
`ask_*` del Orchestrator lo **extrae**, lo publica en una cola de la petición y entrega al modelo solo el
texto (así el modelo no copia JSON extenso ni lo altera). El *entrypoint* mezcla esa cola con el stream del
modelo. Las Tools de negocio publican de forma análoga el resultado de la API.

## 7. Tools del Orchestrator [RF-90..99]

| Tool | Parámetros | Backend |
|---|---|---|
| `create_trip` | name, origin, destination, startDate, endDate, travelers, budgetCOP, notes? | `POST /trips` |
| `get_trips` | tripId? | `GET /trips[/{id}]` |
| `update_trip` | tripId + campos | `PATCH /trips/{id}` |
| `create_itinerary` | tripId, days[] | `POST /trips/{id}/itinerary` |
| `update_itinerary` | tripId, days[] | `PUT /trips/{id}/itinerary` |
| `create_reservation` | tripId, kind, title, priceCOP, details, link?, pay, idempotencyKey? | `POST /reservations` o `/purchases` |
| `get_reservations` | tripId? | `GET /reservations` |
| `update_reservation` | reservationId, status?/tripId?/campos | `PATCH /reservations/{id}` |
| `get_wallet`, `top_up_wallet` | amountCOP | `GET /wallet`, `POST /wallet/topup` |
| `convert_currency` | amount, from_currency, to_currency | `GET /fx` → Lambda `utils` → API pública de tasas (sin clave) |
| `compare_transport` | origin, destination | `GET /transport` → Lambda `utils` (geocodificación Open-Meteo + velocidades y esperas estimadas) |
| `ask_flights/weather/hotels` | request | A2A (SigV4) |

Las Tools devuelven al modelo un resumen compacto y al frontend el objeto completo vía evento `ui`.
`create_reservation` con `pay=true` solo debe usarse si el usuario confirmó la compra explícitamente
(instrucción de sistema).

### 7.0 Historial de conversaciones en la memoria del agente [RF-12, RF-14]
La memoria de AgentCore ya conserva cada mensaje de la sesión (`actor = sub`). Se aprovecha como almacén del historial: el Orchestrator guarda además, al final de
cada turno, las tarjetas mostradas en un evento del actor `ui-<sub>` (misma memoria; evita contaminar la restauración de Strands). La Lambda `conversations`
(solo permisos `ListSessions/ListEvents/DeleteEvent` sobre esa memoria) une ambos actores por marca de tiempo y devuelve cada turno como `[herramientas, tarjetas, texto]`.
El actor sale siempre del JWT. Decisión: no duplicar el historial en DynamoDB — la memoria es la fuente del historial conversacional; DynamoDB sigue siendo la
fuente de verdad del negocio.

### 7.1 Barandillas deterministas del agente [RNF-18]
Las pruebas con el modelo real (Gemini flash-lite) mostraron que las reglas solo en el prompt no bastan: llegó a cobrar sin confirmar y a
inventar un enlace de reserva. Por eso se hacen cumplir en código (`ui.py`): `purchase_gate` (compra solo tras un resumen en un turno anterior
y confirmación afirmativa del usuario), `topup_allowed` (recarga solo si el usuario la pide) y `known_link` (solo enlaces entregados por un
especialista). Cubierto por pruebas unitarias (`tests/test_agent_guards.py`).

## 8. Seguridad [RNF-10..17]
- **Sin secretos en el navegador:** solo `VITE_API_URL`, `VITE_AGENT_URL`, `VITE_USER_POOL_ID`, `VITE_CLIENT_ID`.
- **Tokens:** *access token* de Cognito (1 h) con refresco; el SDK lo guarda en `localStorage`
  (riesgo XSS mitigado con CSP en CloudFront y sin `dangerouslySetInnerHTML`).
- **CORS de la API** restringido a la URL de CloudFront y a `http://localhost:5173`.
- **Throttling** del *stage*: 20 req/s, ráfaga 40.
- **Errores genéricos** al cliente; trazas solo en CloudWatch.
- **S3** sin acceso público; CloudFront accede mediante *Origin Access Control*.
- **Sin datos de tarjeta:** el modelo de datos no tiene esos campos y la recarga solo recibe un monto.
- **Cabeceras de seguridad** en CloudFront (HSTS, X-Content-Type-Options, X-Frame-Options, CSP).

## 9. Frontend

Rutas: `/login`, `/` (Dashboard), `/chat`, `/flights`, `/weather`, `/trips`, `/trips/:id`, `/reservations`,
`/wallet`. Estado servidor mediante un cliente `api.js`; chat mediante `agent.js` (parser SSE). Para evitar
datos desactualizados, el chat emite un evento global cuando una Tool de negocio modifica datos y las pantallas
abiertas se recargan [CA-6]. Los módulos de Vuelos y Clima invocan al **mismo Orchestrator** con una petición
estructurada y renderizan los eventos `ui` [RF-23].

## 10. Decisiones y compromisos
| Tema | Decisión | Alternativa |
|---|---|---|
| Identidad en tools | JWT del usuario reenviado a API | Pasar `userId` como parámetro (inseguro) |
| Datos de vuelo en compra | El precio lo aporta el agente; la simulación lo acepta | Revalidar con el proveedor (fuera de alcance) |
| Datos de bus | Estimaciones declaradas como tales | Proveedor real de buses (no hay API abierta) |
| Auto-confirmación de registro | PreSignUp lambda (demo) | Verificación por correo en producción |
| Una tabla | Menos costo y latencia; patrones conocidos | Varias tablas (más simple de leer, más joins) |
