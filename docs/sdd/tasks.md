# Plan de tareas — TripPlanner AI

> Estado: `[ ]` pendiente · `[~]` en curso · `[x]` hecha y verificada.
> Cada tarea referencia los requisitos (`requirements.md`) y la sección de diseño (`design.md`) que cumple.
> Orden: se prioriza el flujo completo (crear viaje → itinerario → reserva → recuperar) y después los extras.

## Etapa 1 — Diseño (días 1–2)
- [x] **T-01** Requisitos, diseño y plan SDD. *(todos)*
- [x] **T-02** Prueba de viabilidad de CORS del endpoint de AgentCore para streaming directo desde el navegador. *(D-01, RNF-02)*

## Etapa 2 — Backend y persistencia (días 3–5)
- [x] **T-10** Plantilla SAM: tabla DynamoDB, Cognito (pool, cliente, trigger PreSignUp), API Gateway HTTP con autorizador JWT, CORS y *throttling*. *(D-03, D-04, RNF-14)*
- [x] **T-11** Código común: respuestas, validación, acceso a tabla, extracción de `sub`. *(RNF-12, RNF-13, RNF-15)*
- [x] **T-12** Lambda `profile`: perfil, preferencias, dashboard. *(RF-03, RF-04, RF-80)*
- [x] **T-13** Lambda `trips`: CRUD de viajes con resumen de presupuesto. *(RF-40, RF-41, RF-44, RF-73)*
- [x] **T-14** Lambda `itineraries`. *(RF-42, RF-43)*
- [x] **T-15** Lambda `reservations` con máquina de estados y reasociación. *(RF-50..54)*
- [x] **T-16** Lambda `wallet`: saldo, recarga, compra atómica, reembolso, idempotencia. *(RF-60..65, RNF-20)*
- [x] **T-17** Pruebas unitarias de validación y de reglas de negocio (con DynamoDB simulada). *(RNF-12)*
- [x] **T-18** Despliegue del backend y pruebas reales con `curl`: éxito, 400, 401, 404, 409. *(CA-1..4)*

## Etapa 3 — Integración agéntica (días 9–11, adelantada por ser el riesgo mayor)
- [x] **T-30** Runtime del Orchestrator con autorizador JWT de Cognito y reenvío de `Authorization`. *(RNF-17, D-03)*
- [x] **T-31** Módulo de Tools de negocio (8 tools + monedero) que llaman a la API con el JWT del usuario. *(RF-90..98, D-02)*
- [x] **T-32** Cola de eventos `ui` y *entrypoint* que la mezcla con el stream. *(RF-13, D-05)*
- [x] **T-33** Salida estructurada en Flights, Weather y Hotels (`<ui>{json}</ui>`). *(RF-22, RF-31, RF-74)*
- [x] **T-34** Tools extra: `convert_currency`, `compare_transport` (respaldadas por la Lambda `utils`). *(RF-70, RF-71)*
- [x] **T-35** Prompt del Orchestrator: flujo del escenario, confirmación antes de comprar, actividades por clima. *(RF-72, RF-61)*
- [x] **T-36** Pruebas reales del Orchestrator desplegado con token de Cognito (streaming y tools). *(RF-10, RF-90..97)*

## Etapa 4 — Frontend (días 6–8)
- [x] **T-50** Proyecto React + Vite, rutas, tema, sesión Cognito (registro, login, logout). *(RF-01, RF-02)*
- [x] **T-51** Cliente `api.js` y cliente de streaming `agent.js` (parser SSE). *(RF-10)*
- [x] **T-52** Chat con streaming, indicadores de herramienta y renderizado de componentes. *(RF-10..14)*
- [x] **T-53** Componentes: `FlightCards`, `WeatherCards`, `HotelCards`, `TripCard`, `ItineraryAgenda`, `ReservationList`, `WalletCard`, `CurrencyCard`, `TransportCard`. *(RF-13)*
- [x] **T-54** Dashboard. *(RF-80)*
- [x] **T-55** Vuelos y Clima (usan el Orchestrator). *(RF-20..24, RF-30..32)*
- [x] **T-56** Mis viajes: lista, formulario, detalle con itinerario editable y presupuesto. *(RF-40..44)*
- [x] **T-57** Reservas: lista con estados, creación, edición, asociación. *(RF-50..54)*
- [x] **T-58** Monedero: saldo, recarga, historial, compra desde tarjeta de vuelo. *(RF-60..63)*
- [x] **T-59** Preferencias de usuario. *(RF-04)*
- [x] **T-60** Despliegue en S3 + CloudFront con cabeceras de seguridad. *(RNF-05)*

## Etapa 5 — Pruebas (días 12–13)
- [~] **T-70** Escenario obligatorio de 12 pasos sobre la infraestructura desplegada. *(sección 6)*
- [x] **T-71** Pruebas de seguridad: sin token, token ajeno, validación, CORS, secretos en el *bundle*. *(CA-1, CA-5)*
- [x] **T-72** Pruebas de persistencia y recuperación tras cerrar sesión. *(RF-41, RF-51, RF-60)*
- [x] **T-73** Pruebas de concurrencia/idempotencia de compra. *(CA-3, CA-4)*

## Etapa 6 — Documentación y entrega (días 14–15)
- [x] **T-90** Diagrama de arquitectura con los dos canales. *(Entregable 4)*
- [x] **T-91** Documentación técnica: arquitectura, modelo de datos, APIs, Lambdas, Tools, integración, ejecución. *(Entregable 6)*
- [~] **T-92** Carpeta de evidencias con registros de ejecución y capturas. *(Entregable 7)*
- [x] **T-93** README actualizado (cuenta nueva, perfil de AWS, despliegue de extremo a extremo).

## Ampliación posterior
- [x] **T-80** Historial de conversaciones en la memoria del agente: persistencia de tarjetas por turno, Lambda `conversations` (listar/abrir/eliminar) y panel lateral de conversaciones (agrupadas por fecha, abrir, eliminar y nueva) en el chat. *(RF-12, RF-14)*
- [x] **T-81** Fondo blanco y tema claro fijo en toda la interfaz.

## Notas de ejecución
- **T-70:** el escenario de 12 pasos se ejecutó de extremo a extremo (evidencia 02). El paso de **vuelos** depende de la cuota mensual del plan de RapidAPI (FlightPowers), que se agotó durante las pruebas: el agente lo informa en lugar de inventar tarifas. El resto del flujo (clima, hoteles, viaje, itinerario, reserva con monedero, recuperación) funciona.
- **T-92:** evidencias 01–05 generadas con scripts reproducibles; capturas de pantalla en `docs/evidencias/capturas/`. El video lo graba el equipo.
- **Descartado por el equipo:** exportación a PDF.
