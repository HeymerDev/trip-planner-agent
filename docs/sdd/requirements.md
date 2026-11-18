# Requisitos — TripPlanner AI

> Metodología: *Spec-Driven Development* (SDD). Este documento define **qué** debe hacer el sistema.
> `design.md` define **cómo**, y `tasks.md` el plan de implementación con su estado.
> Cada requisito tiene un identificador estable (`RF-xx`, `RNF-xx`) que se referencia desde el diseño,
> las tareas y las evidencias de prueba.

## 1. Contexto y alcance

TripPlanner ya cuenta con una solución multiagente (Orchestrator, Flights, Weather y Hotels) desplegada
en Amazon Bedrock AgentCore. El trabajo final la convierte en una **aplicación web completa**:
frontend, backend serverless con persistencia en DynamoDB, autenticación de usuarios y nuevas Tools
que permiten al agente operar el negocio (viajes, itinerarios, reservas) además de conversar.

**Restricción no negociable (RNF-01):** se conservan los agentes existentes. Ninguna lógica de
agentes se simula en el frontend.

### Fuera de alcance
- Pagos reales, captura de datos de tarjeta (prohibido por el enunciado).
- Confirmación de reservas por proveedores reales (el estado `CONFIRMADA` existe en el modelo pero
  el sistema solo produce `SIMULADA` y `PENDIENTE`).
- Exportación a PDF (descartada por el equipo).

## 2. Actores

| Actor | Descripción |
|---|---|
| **Viajero** | Usuario autenticado que planifica y gestiona sus viajes desde la web. |
| **Orchestrator Agent** | Interpreta la intención, delega en especialistas y usa Tools de negocio. |
| **Agentes especialistas** | Flights, Weather y Hotels (A2A + MCP). |
| **Backend de negocio** | API Gateway + Lambdas + DynamoDB. |

## 3. Requisitos funcionales

### A. Autenticación y cuenta
| ID | Requisito |
|---|---|
| RF-01 | El sistema debe permitir registrarse e iniciar sesión con correo y contraseña (Amazon Cognito). |
| RF-02 | Todas las pantallas excepto login/registro deben requerir una sesión válida. |
| RF-03 | Cada usuario debe tener un perfil (`id`, correo, nombre) creado automáticamente en su primer acceso. |
| RF-04 | El usuario debe poder consultar y editar sus **preferencias** de viaje (presupuesto por defecto, tipo de actividades, aerolíneas favoritas, restricciones). |

### B. Asistente conversacional
| ID | Requisito |
|---|---|
| RF-10 | El usuario debe poder enviar mensajes al Orchestrator y recibir la respuesta **por streaming HTTP**, token a token. |
| RF-11 | La interfaz debe mostrar indicadores de procesamiento, incluyendo qué agente o herramienta está trabajando. |
| RF-12 | La conversación debe mantener contexto entre mensajes y entre sesiones (memoria de AgentCore). |
| RF-13 | Cuando el agente produzca datos estructurados (vuelos, clima, viajes, itinerarios, reservas, saldo), la interfaz debe renderizarlos como **componentes visuales** y no solo como texto (*Agent-Driven UI*). |
| RF-14 | El chat debe permitir iniciar una conversación nueva y retomar una anterior. Las conversaciones se guardan en la **memoria del agente** (AgentCore Memory), sobreviven al cierre del navegador y pueden eliminarse. |

### C. Vuelos
| ID | Requisito |
|---|---|
| RF-20 | El usuario debe poder consultar vuelos indicando origen, destino y fechas (ida o ida y vuelta). |
| RF-21 | Cada resultado debe mostrar aerolínea, horarios, duración, escalas y precio cuando exista. |
| RF-22 | Los resultados deben presentarse en **tarjetas comparativas**, con marcas de "más barato" y "más rápido". |
| RF-23 | Los vuelos deben provenir del agente Flights vía MCP; nunca de datos fijos del frontend. |
| RF-24 | Cada tarjeta debe ofrecer el enlace de compra del proveedor y la acción "Reservar (simulado)". |

### D. Clima
| ID | Requisito |
|---|---|
| RF-30 | El usuario debe poder consultar el clima de un destino para unas fechas. |
| RF-31 | Se debe mostrar temperatura mínima/máxima, condición y probabilidad de lluvia cuando la fuente lo ofrezca, en **tarjetas por día**. |
| RF-32 | Si las fechas superan el horizonte de la fuente (16 días), el sistema debe indicarlo en lugar de inventar datos. |

### E. Planificación de viajes
| ID | Requisito |
|---|---|
| RF-40 | El usuario debe poder crear un viaje con destino, origen, fechas, número de viajeros, presupuesto (COP) y preferencias, desde el formulario **y** pidiéndoselo al agente. |
| RF-41 | El usuario debe poder listar, consultar, editar y eliminar sus viajes desde la UI y mediante el agente. |
| RF-42 | El usuario debe poder generar y modificar un **itinerario** por día asociado a un viaje (formulario o agente). |
| RF-43 | El itinerario debe verse en formato agenda por día, con hora, actividad, lugar y costo estimado. |
| RF-44 | Un viaje debe mostrar un resumen de presupuesto: estimado vs. gastado en reservas. |

### F. Reservas
| ID | Requisito |
|---|---|
| RF-50 | El usuario debe poder registrar reservas de **vuelos, hoteles y actividades** asociadas a un viaje. |
| RF-51 | El usuario debe poder listar, consultar, editar y cancelar sus reservas, desde la UI y mediante el agente. |
| RF-52 | Cada reserva tiene un estado `SIMULADA`, `PENDIENTE`, `CONFIRMADA` o `CANCELADA`, mostrado con etiqueta visible en listado y detalle. |
| RF-53 | Todas las reservas creadas por el sistema deben ser `SIMULADA` y estar persistidas en DynamoDB. |
| RF-54 | Una reserva debe poder reasociarse a otro viaje del mismo usuario. |

### G. Monedero simulado (extra)
| ID | Requisito |
|---|---|
| RF-60 | Cada usuario tiene un saldo en COP; puede **recargarlo** con un monto simulado, sin datos de tarjeta ni de pago. |
| RF-61 | Al "comprar" un vuelo, hotel o actividad, el sistema debe descontar el precio del saldo y crear la reserva `SIMULADA` en una **única operación atómica**. |
| RF-62 | Si el saldo es insuficiente, la compra debe rechazarse con un mensaje claro y sin efectos parciales. |
| RF-63 | Debe existir un historial de movimientos (recargas, compras, reembolsos). |
| RF-64 | Al cancelar una reserva pagada con el monedero, el sistema debe reembolsar el monto una sola vez. |
| RF-65 | Una compra repetida con la misma clave de idempotencia no debe descontar dos veces. |

### H. Capacidades adicionales del agente (extras)
| ID | Requisito |
|---|---|
| RF-70 | **Divisas:** el agente debe convertir montos entre monedas (por ejemplo USD→COP) con tasas actuales, indicando fuente y fecha de la tasa. |
| RF-71 | **Bus vs. avión:** dado origen y destino, el agente debe comparar el tiempo puerta a puerta y recomendar bus o avión, aclarando que los datos de bus son estimaciones. |
| RF-72 | **Actividades por ciudad:** el agente debe proponer planes por día para un destino, adaptados a preferencias, presupuesto y clima (por ejemplo, actividades de interior si hay lluvia), y poder guardarlos como itinerario. |
| RF-73 | **Comparador de presupuesto:** el sistema debe contrastar el presupuesto del viaje con el costo de vuelos, hotel y actividades registrados. |
| RF-74 | **Hoteles:** el agente Hotels debe ofrecer alojamientos reales con enlace de reserva. |

### I. Dashboard
| ID | Requisito |
|---|---|
| RF-80 | La pantalla inicial debe mostrar próximos viajes, reservas recientes, saldo del monedero y accesos rápidos. |

## 4. Requisitos de Tools del agente

El Orchestrator debe disponer de Tools respaldadas por Lambda (RF-90 a RF-97) además de las que
delegan en agentes especialistas. Los datos de negocio solo se modifican mediante estas Tools.

| ID | Tool | Operación de negocio |
|---|---|---|
| RF-90 | `create_trip` | Crear un viaje |
| RF-91 | `get_trips` | Consultar viajes |
| RF-92 | `update_trip` | Actualizar un viaje |
| RF-93 | `create_itinerary` | Crear el itinerario de un viaje |
| RF-94 | `update_itinerary` | Modificar un itinerario |
| RF-95 | `create_reservation` | Registrar una reserva (incluye compra con monedero) |
| RF-96 | `get_reservations` | Consultar reservas |
| RF-97 | `update_reservation` | Actualizar una reserva o su estado |
| RF-98 | `get_wallet` / `top_up_wallet` | Consultar saldo y recargar (extra) |
| RF-99 | `convert_currency`, `compare_transport` | Divisas y bus vs. avión (extras) |

## 5. Requisitos no funcionales

### Arquitectura
| ID | Requisito |
|---|---|
| RNF-01 | Se conservan los agentes Orchestrator, Flights, Weather (y Hotels). Está prohibido sustituirlos por lógica en el frontend o un agente único. |
| RNF-02 | Existen **dos canales independientes**: (1) negocio: Frontend → API Gateway → Lambda → DynamoDB; (2) agéntico: Frontend → HTTP streaming → AgentCore → Orchestrator. API Gateway **no** intermedia el streaming. |
| RNF-03 | El frontend **nunca** accede directamente a DynamoDB. |
| RNF-04 | Infraestructura como código: todo el backend en una plantilla AWS SAM; los agentes con el CLI de AgentCore. |
| RNF-05 | El frontend se publica en S3 (con CloudFront para HTTPS). |
| RNF-06 | La memoria de agente **no** sustituye la persistencia: DynamoDB es la fuente de verdad. |

### Seguridad
| ID | Requisito |
|---|---|
| RNF-10 | Roles IAM de mínimo privilegio para cada Lambda y para cada agente. |
| RNF-11 | Ninguna credencial AWS ni secreto en el código del navegador. |
| RNF-12 | Las Lambdas validan tipos, rangos, fechas, longitudes y estados permitidos. |
| RNF-13 | Control de acceso por usuario: la identidad se toma **siempre del token** verificado, nunca de un parámetro del cliente ni del modelo. Un usuario no puede leer ni modificar datos de otro. |
| RNF-14 | API Gateway exige autorización JWT, CORS restringido a los orígenes de la aplicación y *throttling*. |
| RNF-15 | Errores con códigos HTTP correctos y mensajes claros, sin exponer detalles internos. |
| RNF-16 | El sistema no solicita ni almacena datos de tarjetas bancarias. |
| RNF-17 | El endpoint del Orchestrator exige un JWT válido de Cognito. |
| RNF-18 | Las acciones con dinero (compra, recarga) y los enlaces guardados no dependen de la obediencia del modelo: se validan en código (confirmación explícita del usuario, enlaces provenientes de especialistas). |

### Calidad
| ID | Requisito |
|---|---|
| RNF-20 | Las operaciones críticas (compra) son atómicas e idempotentes. |
| RNF-21 | La interfaz es responsive y accesible (contraste, foco visible, etiquetas). |
| RNF-22 | El flujo completo se puede ejecutar de forma real sobre la infraestructura desplegada. |
| RNF-23 | La documentación permite desplegar y probar desde cero. |

## 6. Escenario de aceptación obligatorio

> "Quiero organizar unas vacaciones de cuatro días en Cartagena. Salgo desde Bogotá, viajo con dos personas
> más y tengo un presupuesto de 5 millones de pesos. Quiero conocer el clima, encontrar vuelos y organizar
> algunas actividades turísticas."

| Paso | Resultado esperado | Requisitos |
|---|---|---|
| 1 | El usuario ingresa (login) | RF-01, RF-02 |
| 2 | Escribe en el asistente y ve la respuesta llegar por streaming | RF-10, RF-11 |
| 3–5 | Orchestrator delega en Flights y Weather | RNF-01, RF-23 |
| 6 | La UI muestra tarjetas de vuelos y de clima | RF-13, RF-22, RF-31 |
| 7 | Pide crear el viaje | RF-40, RF-90 |
| 8 | Se genera el itinerario | RF-42, RF-93, RF-72 |
| 9 | Se registra una reserva simulada (compra con monedero) | RF-50, RF-53, RF-61 |
| 10 | Los datos quedan en DynamoDB | RF-53, RNF-06 |
| 11–12 | Cierra la app, vuelve a entrar y recupera viajes, itinerario, reservas y saldo | RF-41, RF-51, RF-60 |

## 7. Criterios de aceptación transversales

- **CA-1** Sin token, cualquier endpoint de negocio responde `401`; con token de otro usuario, un recurso ajeno responde `404` (no revela su existencia).
- **CA-2** Un cuerpo inválido responde `400` con la lista de campos erróneos.
- **CA-3** Dos compras con la misma clave de idempotencia descuentan una sola vez.
- **CA-4** Una compra con saldo insuficiente responde `409` y no cambia saldo ni reservas.
- **CA-5** El navegador solo contiene: URL de la API, URL del runtime, IDs públicos de Cognito.
- **CA-6** El agente puede crear un viaje por chat y el viaje aparece en "Mis viajes" sin recargar manualmente la base de datos (y viceversa).
