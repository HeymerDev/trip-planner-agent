# tripplanner (trip-planner-a2a)

> ## Trabajo final: TripPlanner AI (aplicación web completa)
>
> El proyecto evolucionó de un playground de agentes a una **plataforma web**: frontend React publicado en S3 + CloudFront,
> backend serverless (API Gateway + Lambda + DynamoDB + Cognito, con AWS SAM) y los agentes de AgentCore con nuevas Tools de negocio.
>
> | Carpeta | Contenido |
> |---|---|
> | [`docs/DOCUMENTACION_TECNICA.md`](docs/DOCUMENTACION_TECNICA.md) | Arquitectura, modelo de datos, APIs, Lambdas, Tools, integración de agentes, seguridad e instrucciones de ejecución |
> | [`docs/sdd/`](docs/sdd/) | Spec-Driven Development: [requisitos](docs/sdd/requirements.md), [diseño](docs/sdd/design.md) y [tareas](docs/sdd/tasks.md) |
> | [`docs/arquitectura.svg`](docs/arquitectura.svg) | Diagrama con los dos canales (también [PNG](docs/arquitectura.png)) |
> | [`docs/evidencias/`](docs/evidencias/) | Evidencias reales: API, agentes por streaming, infraestructura, pruebas, seguridad, capturas |
> | `backend/` | Plantilla SAM (`template.yaml`), Lambdas (`src/`), pruebas (`tests/`) y scripts de evidencia (`scripts/`) |
> | `frontend/` | React + Vite (diseño basado en Stitch, ver [`docs/diseno-stitch/`](docs/diseno-stitch/)) |
> | `app/`, `agentcore/` | Los 4 agentes (Orchestrator, Flights, Weather, Hotels) y su configuración de AgentCore |
>
> **Aplicación publicada:** https://d33bzx67i3x8j6.cloudfront.net · **API:** `https://1uyl298pkh.execute-api.us-east-2.amazonaws.com`
>
> **Despliegue resumido** (cuenta `406868032460`, región `us-east-2`):
> ```powershell
> $env:AWS_PROFILE = "nueva"      # IMPORTANTE: sin esto la CLI usa la cuenta anterior y falla
> cd backend ; sam build ; sam deploy                  # tabla, Cognito, API, Lambdas, S3, CloudFront
> cd .. ; agentcore deploy --yes                       # los 4 agentes
> cd frontend ; npm install ; npm run build
> aws s3 sync dist/ s3://<FrontendBucketName> --delete
> aws cloudfront create-invalidation --distribution-id <DistributionId> --paths "/*"
> ```
> Detalle completo en la sección 11 de la documentación técnica. La cuenta de prueba de la demostración está en `DEMO_USER.txt` (no versionado).

---

## Playground de agentes (base del proyecto)

Workshop de un planificador de viajes multi-agente construido con
[Strands Agents](https://strandsagents.com/) y desplegado en
**AWS Bedrock AgentCore Runtime**. Cuatro agentes colaboran entre si mediante
el protocolo **A2A (Agent-to-Agent)**, generado con el CLI real de AgentCore
(`agentcore create` / `agentcore add agent`).

- **FlightsAgent**: busca vuelos **reales** (tarifas en vivo de Google Flights) con el
  MCP alojado de FlightPowers (`https://flights.flightpowers.com/mcp`):
  `search_oneway_flights` y `search_roundtrip_flights`. Requiere una credencial (ver
  "Credencial de vuelos"). Servidor A2A.
- **WeatherAgent**: entrega el clima **real** con el MCP `mcp-weather-server` de PyPI
  (Open-Meteo, sin API key), version fijada en 0.6.1; usa `get_current_weather` y
  `get_weather_byDateTimeRange`. Es **Python puro**: lo lanza como subproceso con el mismo
  Python del entorno, sin Node, y viaja como una dependencia mas en un runtime Python. El
  pronostico real solo llega a unos 16 dias; para fechas mas lejanas (o pasadas) el agente
  lo dice en vez de inventarlo. Servidor A2A.
- **HotelsAgent**: busca hospedaje **real** con el MCP publico de Staylist World
  (`https://staylist.world/mcp`, gratuito, sin registro ni API key): `search_hotels`,
  `get_hotel`, `get_booking_link`, `list_destinations`. Servidor A2A.
- **OrchestratorAgent**: agente conversacional que recibe la solicitud del
  usuario, consulta a los tres especialistas como cliente A2A
  (`strands.agent.a2a_agent.A2AAgent`) y consolida sus respuestas en un plan
  de viaje. Se despliega como runtime HTTP (`bedrock_agentcore.runtime.BedrockAgentCoreApp`).

Los datos de **hoteles** (MCP de Staylist World), **vuelos** (MCP de FlightPowers, con su
credencial) y **clima** (MCP weather-mcp) son **reales**; solo las herramientas del
gateway (`TravelTips`) siguen con datos simulados. Staylist
muestra precios observados antes (no en vivo) y sus enlaces de reserva son de socios
(Trip.com / Klook) con los que Staylist puede ganar una comision; el servicio no
permite reservar ni cobrar. La URL se puede cambiar con la variable `HOTELS_MCP_URL`.
Para la autenticacion entre agentes ver "Autenticacion (AgentCore Identity)".

Los 4 agentes usan **Google Gemini** como proveedor de modelo (no Bedrock
model access) y los 4 tienen **memoria por conversacion** via Bedrock
AgentCore Memory.

## Estructura real del proyecto

Generada por el CLI (`agentcore create` + `agentcore add agent` x3), no a mano:

```
tripplanner/
├── AGENTS.md                     # contexto para asistentes de IA sobre el proyecto
├── agentcore/
│   ├── agentcore.json            # config del proyecto (4 runtimes + memoria + envVars)
│   ├── aws-targets.json          # cuenta/region de despliegue
│   └── cdk/                      # infraestructura CDK (@aws/agentcore-cdk)
└── app/
    ├── FlightsAgent/{main.py, pyproject.toml, model/load.py}
    ├── WeatherAgent/{main.py, pyproject.toml, model/load.py}
    ├── HotelsAgent/{main.py, pyproject.toml, model/load.py}
    ├── OrchestratorAgent/{main.py, pyproject.toml, model/load.py, mcp_client/client.py}
    └── TravelTips/{handler.py, pyproject.toml}   # Lambda del target del gateway
dev/local_gateway.py                              # sustituto local del gateway (valida JWT de Cognito)
dev-all.ps1                                       # levanta todo en local (5 ventanas)
```

Cada agente tiene su propio entorno virtual (`uv sync`) y su `pyproject.toml`
en vez de `requirements.txt` (asi es como lo genera el CLI real para builds
`CodeZip`).

## Modelo: Google Gemini

Cada agente carga el modelo (`gemini-3.5-flash-lite`) en `app/<Agente>/model/load.py`.
La API key se resuelve asi:

- **Local** (`agentcore dev`, `dev-all.ps1`): variable `AGENTCORE_CREDENTIAL_GEMINI`
  o `GEMINI_API_KEY`, leidas de `agentcore/.env.local` (gitignored).
- **Desplegado**: la key ya **no** esta en `agentcore.json`; el runtime se la pide
  a AgentCore Identity (credencial `Gemini`) con `@requires_api_key`. Ver
  "Autenticacion (AgentCore Identity)".

> Nota: `agentcore add credential` cifra los secretos de `.env.local`
> (`enc:v1:...`). `agentcore dev` los descifra solo, pero `dev-all.ps1` arranca los
> especialistas con `python main.py` y necesita `GEMINI_API_KEY` en texto plano en
> esa linea (la linea `AGENTCORE_CREDENTIAL_GEMINI` se deja como la escribio el CLI).

Con esto **ya no hace falta Bedrock Model Access** para que los agentes
respondan (ese bloqueo quedaba del lado de AWS). Lo que si sigue haciendo
falta es la cuota de AgentCore Runtime (ver abajo) porque eso es sobre el
*host* de los agentes, no sobre que LLM usan.

## Memoria (Bedrock AgentCore Memory)

Hay un recurso de memoria compartido, `TripPlannerMemory`, definido en
`agentcore/agentcore.json` → `memories[]` con las 3 estrategias del workshop:
`USER_PREFERENCE` (TravelerPreferences), `SUMMARIZATION` (SessionSummarizer) y
`SEMANTIC` (TravelFacts), cada una con su `namespaceTemplates`. Los 4 agentes lo consumen via
`MEMORY_ID` (variable de entorno) y `bedrock_agentcore.memory.integrations.strands`:

- Los 3 especialistas (`FlightsAgent`, `WeatherAgent`, `HotelsAgent`) pasaron
  de un `Agent` global a una **fabrica** `create_agent(context_id)` (patron
  recomendado por `StrandsA2AExecutor(agent_factory=...)`), donde cada
  contexto A2A obtiene su propio `AgentCoreMemorySessionManager` con
  `session_id=context_id`.
- `OrchestratorAgent` mantiene su cache LRU en memoria de proceso (para
  respuesta rapida dentro de una misma instancia tibia) y ademas adjunta un
  `AgentCoreMemorySessionManager` por `session_id` (para que la historia
  sobreviva a un cold start).
- `OrchestratorAgent` toma el `actor_id` del contexto de la invocacion
  (`context.actor_id`, por defecto `"default-user"`), asi `{actorId}` en los
  namespaces separa los recuerdos por usuario. Los especialistas usan un `actor_id`
  fijo por agente (`"FlightsAgent"`, `"WeatherAgent"`, `"HotelsAgent"`) porque A2A
  solo les entrega un `context_id`, no la identidad del usuario final.

`MEMORY_ID` se llena igual que las URLs de los especialistas: recien se sabe
despues del primer `agentcore deploy` (ver "Orden de despliegue").

## Enlaces en las respuestas

Los especialistas devuelven enlaces utiles (reserva de hoteles de Staylist, compra de vuelos de
Google Flights). El orquestador los perdia al "consolidar" porque su prompt pedia una respuesta
breve sin decirle que los conservara, y porque recibia el texto del especialista como `str()`
de un diccionario. Ahora `_message_text` le pasa el texto limpio y el prompt le exige incluir
cada URL como `[texto](url)`, copiada tal cual, junto a su opcion. Si cambias el prompt,
conserva esa regla.

## Credencial de vuelos (FlightPowers)

Listar las herramientas del MCP de FlightPowers no pide credenciales, pero **ejecutar una
busqueda si**. Hay dos formas de conseguirla; ambas las crea el propio usuario:

1. **Clave de RapidAPI** (la forma preferida por FlightPowers): suscribirse a la API
   *Google Flights Live* en RapidAPI (plan BASIC gratuito: 10 busquedas al mes) y copiar su
   `x-rapidapi-key`. Se envia en la cabecera `x-rapidapi-key`.
2. **Inicio de sesion con Google** en `https://google-flights-mcp.flightpowers.com/connect`:
   da 10 busquedas gratis por dia con la clave de FlightPowers y entrega una URL
   `...mcp?fp_token=fpk_...`; el token `fpk_...` (credencial de 90 dias) se envia como
   `Authorization: Bearer`. A cambio, ese servicio guarda tu id de cuenta de Google y tu correo.

Guardala en `agentcore/.env.local` (gitignored), en texto plano, con **una** de estas lineas:

```
FLIGHTS_RAPIDAPI_KEY=tu-clave-de-rapidapi
FLIGHTS_MCP_TOKEN=fpk_tu-token
```

`dev-all.ps1` se la pasa a `FlightsAgent`. Sin credencial, `FlightsAgent` no ofrece herramientas
y responde que los vuelos no estan configurados (probado: sin credencial la llamada al MCP se
queda colgada por un desafio OAuth 401 que el cliente no maneja, por eso se evita). El plan
gratuito es chico: una busqueda es una combinacion fecha x destino, asi que un rango de varios
dias gasta varias. Si mas adelante se despliega, la clave debe pasar a una credencial de
AgentCore Identity como la de Gemini, no a `agentcore.json` en texto plano.

## Autenticacion (AgentCore Identity)

Mapa del diagrama de Identity de la consola contra este proyecto:

| Pieza | Implementacion |
|---|---|
| **Agent Inbound Auth** (quien llama a un runtime) | `authorizerType: "AWS_IAM"` explicito en los 4 runtimes de `agentcore.json`. Un runtime no admite modo sin autenticacion: solo `AWS_IAM` o `CUSTOM_JWT`. |
| **Agent Outbound Auth → agentes (IAM)** | `OrchestratorAgent` firma con SigV4 (servicio `bedrock-agentcore`) sus llamadas A2A a los especialistas: `SigV4HttpxAuth` + `_ask_remote` en `app/OrchestratorAgent/main.py`. Se activa con `A2A_AUTH_MODE=sigv4` (puesto en `agentcore.json`); en local queda en `none` porque los especialistas locales no validan nada. |
| **Agent Outbound Auth → externos (API key)** | Credencial `Gemini` (`agentcore add credential`, `ApiKeyCredentialProvider`) + `@requires_api_key(provider_name="Gemini")` en `model/load.py`. |
| **Agent Outbound Auth → Gateway (OAuth)** | `OrchestratorAgent` pide un access token OAuth (M2M / `client_credentials`) y lo manda como `Bearer` al gateway por MCP: `app/OrchestratorAgent/mcp_client/client.py`. Desplegado lo entrega AgentCore Identity (`@requires_access_token`, credencial `TripPlannerGateway-oauth`); en local lo pide directo a Cognito. |
| **Gateway Inbound Auth** | `TripPlannerGateway` (MCP) con `authorizerType: CUSTOM_JWT` contra Cognito (`discoveryUrl`, `allowedClients`, `allowedScopes`). |
| **Gateway targets** | Target `TravelTips` (Lambda en `app/TravelTips/`, datos simulados) con dos herramientas: `get_travel_tips` y `convert_cop_to_usd`. |
| **Target Outbound Auth** | `outboundAuth: NONE` en `agentcore.json`: un target Lambda no usa OAuth, el gateway lo invoca con su rol de IAM. |

### Gateway y OAuth (Amazon Cognito)

El proveedor OAuth es **Amazon Cognito**, creado en la cuenta `042449721463` (us-east-2):

| Recurso | Valor |
|---|---|
| User pool | `us-east-2_Ioci9CSrv` (`tripplanner-gateway`) |
| Dominio | `tripplanner-gw-7f47e7` |
| Resource server / scope | `tripplanner-gateway` / `tripplanner-gateway/invoke` |
| App client (M2M, `client_credentials`) | `tripplanner-orchestrator` (`2ok8hlm2d7h4fg6eecsg7biggb`) |

Los access tokens de Cognito no traen `aud`, por eso el gateway valida con `allowedClients` (claim `client_id`) y `allowedScopes`, no con `allowedAudience`.

El client id/secret estan en `agentcore/.env.local` (cifrados por el CLI). **Costo:** los clientes M2M de Cognito pueden cobrar una tarifa mensual pequena mas las solicitudes de token; confirma el precio vigente en la pagina de precios de Cognito. Para eliminar todo:

```powershell
aws cognito-idp delete-user-pool-domain --user-pool-id us-east-2_Ioci9CSrv --domain tripplanner-gw-7f47e7 --region us-east-2
aws cognito-idp delete-user-pool --user-pool-id us-east-2_Ioci9CSrv --region us-east-2
```

(luego `agentcore remove gateway` y, si quieres, `agentcore remove credential`).

### Probarlo en local sin desplegar

El gateway real no se puede desplegar, asi que `dev/local_gateway.py` hace de sustituto: valida el JWT de Cognito de verdad (firma contra el JWKS, emisor, cliente y scope, leidos de `agentcore.json`) y sirve las mismas herramientas reutilizando `app/TravelTips/handler.py`. `dev-all.ps1` lo arranca (puerto 8090) y apunta el orquestador a el. Prueba en la UI: *"Dame consejos para viajar a Cartagena y cuanto son 2000000 COP en USD"*.

Si lo vuelves a lanzar sin cerrar la corrida anterior, `dev-all.ps1` se niega a arrancar y avisa
que hay puertos ocupados (8080, 8081, 8090, 9000-9002): un orquestador viejo seguiria
respondiendo con codigo desactualizado mientras el nuevo falla al enlazar el puerto. Cierra las
ventanas anteriores o usa `.\dev-all.ps1 -FreePorts`, que detiene lo que escuche en esos puertos
(incluidos los procesos hijos huerfanos que deja `uvicorn --reload`).

Una vez desplegado, `GATEWAY_URL` (hoy `"https://"` en `agentcore.json`) se reemplaza por la URL del gateway que muestra `agentcore status`, igual que las URLs de los especialistas. El orquestador sigue funcionando sin el gateway si esa URL no esta puesta o no se puede obtener el token.

Que esta verificado y que no:

- Verificado en local: `agentcore validate`; la firma SigV4 (cabecera `Authorization`
  con alcance `us-east-2/bedrock-agentcore`, cuerpo intacto); el flujo completo
  orquestador → especialistas en modo `none` y en modo `sigv4`.
- Verificado de verdad contra Cognito (real, no simulado): se obtiene un token
  `client_credentials` con `client_id` y `scope` correctos; el gateway local lo valida y
  rechaza con 401 las peticiones sin token o con token invalido; el orquestador llama a
  `TravelTips___get_travel_tips` y `TravelTips___convert_cop_to_usd` desde el LLM, tambien
  arrancado con `agentcore dev` (que descifra las credenciales de `.env.local`); con un
  secreto OAuth incorrecto el orquestador sigue respondiendo sin las herramientas del gateway.
- **No verificado contra AWS** (no se puede desplegar): que el endpoint del runtime
  acepte esa firma, que el credential provider exista y entregue la key, que el rol
  de ejecucion del runtime tenga permiso para leerla, que el `AgentCore Gateway` real acepte
  el token de Cognito con esa configuracion, y que invoque la Lambda `TravelTips`.

## Requisitos previos

- Node.js 20+ (el CLI `agentcore` es un paquete npm: `npm install -g @aws/agentcore`)
- Python 3.12 y [`uv`](https://docs.astral.sh/uv/) para los entornos de cada agente
- AWS CLI configurado con credenciales validas
- Una **API key de Gemini** (ver seccion de arriba)
- Una cuenta de AWS con:
  - **Cuota `Total Agents per Account` de Bedrock AgentCore Runtime > 0** (Service Quotas → Amazon Bedrock AgentCore). Cuentas nuevas suelen arrancar en 0 y hay que pedir el aumento (`aws service-quotas request-service-quota-increase --service-code bedrock-agentcore --quota-code L-F4575653 --desired-value 1001`) y esperar aprobacion de AWS. Esto es necesario sin importar el proveedor de modelo, porque es cuota del *runtime* (el host de los agentes), no del LLM.
  - Permisos amplios (idealmente `AdministratorAccess`) para el usuario que corre `agentcore deploy`: CDK bootstrap crea roles IAM, un bucket S3, un repo ECR y un parametro SSM, y el `CloudFormationExecutionRole` que hace el trabajo real ya recibe `AdministratorAccess` por defecto — recortar permisos del lado del usuario que despliega no evita eso, solo genera bloqueos en cascada.

## Orden de despliegue

El `OrchestratorAgent` necesita las URLs publicas de `FlightsAgent`,
`WeatherAgent` y `HotelsAgent` para invocarlos por A2A, y los 4 agentes
necesitan el `MEMORY_ID` real. El despliegue va en dos pasadas:

1. Poner la API key de Gemini en los 4 `envVars.GEMINI_API_KEY`.
2. Bootstrap de CDK una sola vez por cuenta/region (`cdk bootstrap`, lo hace `agentcore deploy` automaticamente la primera vez).
3. `agentcore deploy` crea los 4 runtimes + la memoria. La primera vez, `OrchestratorAgent` queda con las URLs y `MEMORY_ID` en placeholder (`"https://"` / `"PENDING_MEMORY_ID"`).
4. `agentcore status` para cada especialista → copiar su URL a `agentcore/agentcore.json`. Para el `MEMORY_ID`, tomar el id de `TripPlannerMemory` (`agentcore status` lo muestra, o `aws bedrock-agentcore-control list-memories`) y pegarlo en los 4 `envVars.MEMORY_ID`.
5. `agentcore deploy` de nuevo: como no se renombra ningun runtime, la actualizacion es in-place (no destruye/recrea los agentes).

## Comandos (PowerShell)

Ejecutar desde `tripplanner/`.

```powershell
agentcore validate
```

```powershell
$env:GEMINI_API_KEY = "tu-api-key-de-gemini"
agentcore dev --runtime FlightsAgent --logs
```

```powershell
agentcore deploy --yes --verbose
```

```powershell
agentcore status --runtime FlightsAgent
agentcore status --runtime WeatherAgent
agentcore status --runtime HotelsAgent
```

Copiar cada URL y el `MEMORY_ID` a `agentcore/agentcore.json` y redesplegar:

```powershell
agentcore deploy --yes --verbose
```

```powershell
agentcore invoke --runtime OrchestratorAgent "Quiero viajar de Bogota a Cartagena el 2026-10-15, dime vuelos, clima y hoteles"
```

```powershell
agentcore logs --runtime OrchestratorAgent
agentcore traces list --runtime OrchestratorAgent
```

## Notas del workshop

- Los `tools` (`search_flights`, `get_forecast`, `search_hotels`, `ask_flights`,
  `ask_weather`, `ask_hotels`) usan **docstrings en espanol**: el LLM del
  agente los lee para decidir cuando invocar cada herramienta.
- Los tres especialistas usan el patron real del toolkit: `serve_a2a(StrandsA2AExecutor(agent_factory=create_agent))`
  de `bedrock_agentcore.runtime` + `strands.multiagent.a2a.executor` — una
  fabrica por `context_id`, no un `Agent` global compartido, para poder
  adjuntar un `session_manager` de memoria aislado por conversacion.
- `OrchestratorAgent` **no importa codigo** de los especialistas: solo los
  conoce por su URL, via `A2AAgent(endpoint=...)` de `strands.agent.a2a_agent`.
- El bootstrap de CDK y el deploy requieren permisos bastante amplios (IAM,
  ECR, S3, SSM ademas de CloudFormation) porque el `CloudFormationExecutionRole`
  que crea los recursos reales recibe `AdministratorAccess` por defecto.
- Cuentas de AWS nuevas pueden tener la cuota `Total Agents per Account` de
  Bedrock AgentCore en 0 — hay que pedir el aumento por Service Quotas antes
  de poder desplegar el primer agente (independiente del proveedor de modelo).
