# Evidencia 02 — Agentes por HTTP streaming (escenario de demostración)

- Fecha: 2026-11-16 06:26 UTC
- Canal: navegador → AgentCore Runtime **directo** (HTTP streaming, SSE) con JWT de Cognito; sesión `9b8085ac-9716-4c4d-b967-bb446b910cd8`
- El Orchestrator delega en Flights / Weather / Hotels por A2A (SigV4) y usa las Tools de negocio (Lambda → DynamoDB).

| Turno | HTTP | Tools invocadas | Componentes de UI emitidos | 1.er byte | Total |
|---|---|---|---|---|---|
| Paso 2-6 | 200 | ask_weather, ask_flights, ask_hotels, convert_currency | weather, hotels, currency | 9.5s | 38s |
| Paso 7 | 200 | create_trip | trip | 0.6s | 3s |
| Paso 8 | 200 | create_itinerary | itinerary | 0.6s | 6s |
| Paso 9a | 200 | top_up_wallet | wallet | 0.5s | 4s |
| Paso 9b | 200 | get_wallet, create_reservation | wallet | 0.5s | 4s |
| Paso 9c | 200 | create_reservation | reservation | 0.5s | 33s |
| Paso 12 | 200 | get_trips, get_reservations, get_wallet | wallet, trip, itinerary, reservations, reservations | 0.6s | 5s |

---

## Paso 2-6 · Consulta del escenario (clima, vuelos, hoteles) — NO debe crear nada todavía

**Usuario:** Quiero organizar unas vacaciones de cuatro días en Cartagena, del 20 al 23 de noviembre de 2026. Salgo desde Bogotá, viajo con dos personas más y tengo un presupuesto de 5 millones de pesos. Quiero conocer el clima, encontrar vuelos y organizar algunas actividades turísticas.

**Herramientas:** ask_weather → ask_flights → ask_hotels → convert_currency  
**Componentes de UI:** weather, hotels, currency

**Respuesta del asistente (texto en streaming):**

> ¡Hola! He recopilado la información para tus vacaciones en Cartagena del **20 al 23 de noviembre de 2026** para **3 viajeros**. 
> 
> Aquí tienes el resumen y la propuesta inicial:
> 
> ### 1. Clima en Cartagena (20 - 23 de noviembre)
> Tendrás días cálidos y mayormente soleados, con temperaturas entre los 26°C y 32°C y sensación térmica que puede alcanzar los 39°C. Habrá alta humedad y posibilidad de algunas lloviznas dispersas o intermitentes (especialmente hacia las tardes o noches), ¡así que lleva ropa fresca y un paraguas ligero!
> 
> ### 2. Vuelos (Bogotá ⇄ Cartagena)
> Actualmente el servicio de búsqueda de vuelos presenta una limitación temporal en su cuota de consultas en vivo. Sin embargo, para 3 personas en temporada regular, un presupuesto estimado de vuelos ronda entre **1.200.000 COP y 1.800.000 COP** en total (ida y regreso).
> 
> ### 3. Alojamiento recomendado
> Una opción céntrica, muy bien calificada y económica dentro de tus opciones es el **Sol de Alba Hotel Boutique** (en el Centro Histórico), con un precio aproximado de **171 USD por noche** (unos **567.145 COP** por noche según la tasa de cambio actual). 
> * Para 3 noches, el costo estimado de hospedaje sería de aproximadamente **1.701.435 COP**.
> 
> ### 4. Propuesta de Actividades Turísticas (Itinerario sugerido)
> * **Día 1 (20 de nov): Llegada y Atardecer**
>   * *14:00* · Check-in en el hotel y descanso del vuelo.
>   * *17:00* · Caminata por las murallas y llegada al **Café del Mar** para ver el atardecer cartagenero. *(Costo aprox. consumo: 100.000 COP)*.
> * **Día 2 (21 de nov): Tour de Islas**
>   * *08:00 - 16:00* · Excursión en lancha a las Islas del Rosario / Playa Blanca (incluye almuerzo típico). *(Costo aprox. por persona: 150.000 COP → 450.000 COP en total)*.
> * **Día 3 (22 de nov): Historia y Cultura**
>   * *09:00* · Recorrido a pie por la Ciudad Amurallada, la Torre del Reloj y el Castillo de San Felipe de Barajas. *(Entrada al castillo aprox. 35.000 COP por persona → 105.000 COP en total)*.
>   * *19:00* · Cena en Getsemaní disfrutando de la arquitectura colonial y ambiente nocturno. *(Costo aprox.: 200.000 COP)*.
> * **Día 4 (23 de nov): Compras y Retorno**
>   * *10:00* · Visita al Mercado de Bazurto o las Bóvedas para comprar artesanías y recuerdos. *(Presupuesto compras: 100.000 COP)*.
>   * *Tarde* · Traslado al aeropuerto para el vuelo de regreso a Bogotá.
> 
> ---
> 
> ### Resumen de presupuesto estimado (para 3 personas):
> * **Hospedaje (3 noches):** ~1.700.000 COP
> * **Vuelos (estimados):** ~1.500.000 COP
> * **Alimentación y actividades:** ~1.000.000 COP
> * **Total estimado:** ~4.200.000 COP (¡Dentro de tu presupuesto de **5.000.000 COP**!).
> 
> *Nota: No he creado ni guardado ningún viaje, itinerario ni reserva todavía, ya que solo me pediste organizar la información y proponer un plan.* 
> 
> ¿Te gusta esta propuesta y deseas que **cree el viaje, guarde este itinerario o proceda con alguna reserva simulada**? ¡Dime y con gusto lo hacemos!

## Paso 7 · El usuario pide crear el viaje

**Usuario:** Perfecto, crea el viaje con esos datos.

**Herramientas:** create_trip  
**Componentes de UI:** trip

**Respuesta del asistente (texto en streaming):**

> ¡Listo! He creado exitosamente tu viaje en el sistema. 
> 
> * **ID del viaje:** `f8d42b6d5c634659`
> * **Nombre:** Vacaciones en Cartagena
> * **Origen / Destino:** Bogotá ➔ Cartagena
> * **Fechas:** Del 20 al 23 de noviembre de 2026
> * **Viajeros:** 3 personas
> * **Presupuesto:** 5.000.000 COP
> * **Estado:** PLANEADO
> 
> Si deseas que guarde el itinerario detallado que conversamos, o si quieres que busquemos algún detalle adicional (como agregar reservas o ajustar actividades), solo dímelo.

## Paso 8 · Se genera y guarda el itinerario

**Usuario:** Genera un itinerario de 4 días con actividades turísticas que quepan en el presupuesto, adaptado al clima, y guárdalo.

**Herramientas:** create_itinerary  
**Componentes de UI:** itinerary

**Respuesta del asistente (texto en streaming):**

> ¡He creado y guardado exitosamente el itinerario para tus vacaciones en Cartagena! 
> 
> Aquí está el resumen día por día con las actividades adaptadas al clima y dentro de tu presupuesto:
> 
> * **Día 1 (20 de noviembre de 2026):**
>   * **14:00** – Llegada y Check-in en el *Hotel Sol de Alba Boutique*.
>   * **17:00** – Atardecer en las Murallas en *Café del Mar* (Costo estimado: 100.000 COP). *Nota: Ideal para disfrutar el inicio de la tarde con precaución por posibles lloviznas ligeras.*
> 
> * **Día 2 (21 de noviembre de 2026):**
>   * **08:00** – Tour de Islas y Playa en las *Islas del Rosario* (Costo estimado: 450.000 COP). *Nota: Día soleado y de alta sensación térmica, perfecto para disfrutar de la playa.*
> 
> * **Día 3 (22 de noviembre de 2026):**
>   * **09:00** – Recorrido Histórico por la Ciudad Amurallada, Torre del Reloj y el *Castillo de San Felipe de Barajas* (Costo estimado: 105.000 COP).
>   * **19:00** – Cena y caminata nocturna en el *Barrio Getsemaní* (Costo estimado: 200.000 COP).
> 
> * **Día 4 (23 de noviembre de 2026):**
>   * **10:00** – Compras de última hora y artesanías en *Las Bóvedas / Centro Histórico* (Costo estimado: 100.000 COP).
>   * **14:00** – Regreso a Bogotá desde el *Aeropuerto Internacional Rafael Núñez*.
> 
> El costo total estimado en actividades y planes para este itinerario es de **955.000 COP**, el cual se ajusta perfectamente a tu presupuesto total de **5.000.000 COP**, dejando margen para vuelos, hospedaje y gastos personales. 
> 
> ¿Hay algo más en lo que te pueda ayudar con este viaje?

## Paso 9a · Recarga del monedero simulado

**Usuario:** Recarga 3.000.000 COP en mi monedero.

**Herramientas:** top_up_wallet  
**Componentes de UI:** wallet

**Respuesta del asistente (texto en streaming):**

> ¡Listo! He recargado con éxito **3.000.000 COP** en tu monedero simulado. 
> 
> Tu saldo actual es de **3.000.000 COP**. 
> 
> ¿Te gustaría que utilicemos parte de este saldo para realizar alguna reserva o compra simulada para tu viaje a Cartagena?

## Paso 9b · Solicita reservar (el agente debe pedir confirmación antes de cobrar)

**Usuario:** Quiero reservar una noche en el hotel que más te guste de los que encontraste.

**Herramientas:** get_wallet → create_reservation  
**Componentes de UI:** wallet

**Respuesta del asistente (texto en streaming):**

> Has seleccionado el **Charleston Santa Teresa Cartagena** (hotel 5 estrellas ubicado en el Centro Histórico, con piscina en la azotea e impresionantes atardeceres).
> 
> * **Detalle:** 1 noche (20 al 21 de noviembre de 2026)
> * **Precio original:** 466 USD (~1.545.553 COP)
> * **Tu saldo actual:** 3.000.000 COP
> * **Saldo restante estimado tras la compra:** 1.454.447 COP
> 
> ¿Confirmas que deseas realizar esta reserva simulada por **1.545.553 COP** y descontarla de tu monedero?

## Paso 9c · Confirmación explícita → compra simulada

**Usuario:** Sí, confirmo la compra con el saldo del monedero.

**Herramientas:** create_reservation  
**Componentes de UI:** reservation

**Respuesta del asistente (texto en streaming):**

> ¡Reserva realizada con éxito! *(Compra simulada)*.
> 
> * **Reserva:** Charleston Santa Teresa · 1 noche (20-21 Nov)
> * **Precio:** 1.545.553 COP (466 USD)
> * **Estado:** SIMULADA y PAGADA
> * **Nuevo saldo en tu monedero:** 1.454.447 COP
> 
> Todo ha quedado registrado en tu viaje a Cartagena. ¿Te puedo ayudar con algo más, como consultar las reservas de tu viaje o agregar alguna otra actividad?

## Paso 12 · Recuperación de datos

**Usuario:** Muéstrame mis viajes, mis reservas y mi saldo.

**Herramientas:** get_trips → get_reservations → get_wallet  
**Componentes de UI:** wallet, trip, itinerary, reservations, reservations

**Respuesta del asistente (texto en streaming):**

> Aquí tienes el resumen actualizado de tu viaje, reservas y monedero:
> 
> ### 1. Viaje: Vacaciones en Cartagena
> * **ID:** `f8d42b6d5c634659`
> * **Ruta:** Bogotá ➔ Cartagena (Del 20 al 23 de noviembre de 2026)
> * **Viajeros:** 3 personas
> * **Estado:** PLANEADO
> * **Resumen de Presupuesto:**
>   * Presupuesto total: 5.000.000 COP
>   * Total reservado (Hotel): 1.545.553 COP
>   * Actividades planeadas en itinerario: 955.000 COP
>   * Saldo disponible en presupuesto: 2.499.447 COP
>   * ¿Supera el presupuesto?: No (`overBudget: false`)
> 
> ### 2. Reservas
> * **Hotel Charleston Santa Teresa · 1 noche (20-21 Nov)**
>   * **Tipo:** HOTEL (SIMULADA y PAGADA)
>   * **Precio:** 1.545.553 COP (466 USD)
>   * **Ubicación:** Centro histórico, Cartagena
> 
> ### 3. Monedero Simulado
> * **Saldo actual:** **1.454.447 COP**
> * **Últimos movimientos:**
>   * Recarga simulada: +3.000.000 COP
>   * Compra de reserva (Charleston Santa Teresa): -1.545.553 COP
> 
> Todo va marchando excelente con la planeación de tus vacaciones. ¿Hay algo más que desees ajustar o consultar?
