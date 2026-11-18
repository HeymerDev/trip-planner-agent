# Evidencias — TripPlanner AI

Todas las evidencias se generaron contra la **infraestructura real desplegada** (cuenta `406868032460`, región `us-east-2`), no contra simulaciones.
Los scripts que las producen están en `backend/scripts/` y pueden volver a ejecutarse.

| # | Evidencia | Qué demuestra | Entregable / criterio |
|---|---|---|---|
| 01 | [API del backend](01-api-backend.md) | Lambdas + API Gateway + DynamoDB funcionando: éxito, 400, 401, 404, 409, aislamiento entre dos usuarios, compra atómica e idempotente, reembolso único, CORS | Entregable 2 y 3 · Backend · Seguridad |
| 02 | [Agentes por HTTP streaming](02-agentes-streaming.md) | Escenario obligatorio con 7 turnos: streaming con JWT, Flights/Weather/Hotels por A2A, Tools de negocio, confirmación antes de cobrar, recuperación de datos | Integración agéntica · Tools |
| 03 | [Infraestructura](03-infraestructura.md) | Inventario real: tabla DynamoDB, 8 Lambdas con sus permisos IAM, 22 rutas con autorizador JWT, Cognito, S3 privado + CloudFront, 4 runtimes de AgentCore | Entregables 1–3 · Arquitectura y seguridad |
| 04 | [Pruebas unitarias](04-pruebas-unitarias.md) | 48 pruebas de backend y 6 de frontend | Backend · Calidad |
| 05 | [Seguridad](05-seguridad.md) | Endpoint del agente exige JWT (401/403), cero secretos en el bundle, cabeceras HSTS/CSP/X-Frame, S3 no público | Seguridad (10 %) |
| 06 | [Historial en la memoria del agente](capturas/13-chat-historial-desde-memoria.png) | Un navegador limpio (sin datos locales) recupera una conversación completa —herramientas, tarjetas y texto— desde la memoria de AgentCore | Memoria · Integración agéntica |
| 07 | [Capturas de la aplicación](capturas/) | La aplicación publicada en CloudFront en uso (login, asistente con tarjetas, viajes, monedero…) | Experiencia de usuario |

## Cómo volver a generarlas
```powershell
cd backend
$env:AWS_PROFILE = "nueva"
.venv\Scripts\python.exe scripts\api_evidence.py   --api-url <ApiUrl> --client-id <ClientId> --origin <FrontendUrl>
.venv\Scripts\python.exe scripts\agent_evidence.py --api-url <ApiUrl> --agent-url <AgentUrl> --client-id <ClientId> --email <correo> --password <clave>
.venv\Scripts\python.exe scripts\infra_evidence.py
.venv\Scripts\python.exe -m pytest -v
```

## Nota sobre el video
El video de la demostración lo graba el equipo siguiendo el guion de la sección 12 de [DOCUMENTACION_TECNICA.md](../DOCUMENTACION_TECNICA.md).
